# This container is used for runing Anaconda unit tests in the controlled environment.
# To find out how to build this container please look on the ./tests/README.rst file.

# The `image` arg will set base image for the build.
# possible values:
#   registry.fedoraproject.org/fedora:35
#   registry.fedoraproject.org/fedora:rawhide
#   registry-proxy.engineering.redhat.com/rh-osbs/ubi9:latest # private source
#   registry.access.redhat.com/ubi8/ubi # public source
ARG image
FROM ${image}
# FROM starts a new build stage with new ARGs. Put any ARGs after FROM unless required by the FROM itself.
# see https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact

# The `git_branch` arg will set git branch of Anaconda from which we are downloding spec file to get
# dependencies.
# possible values:
#   master
#   f35-devel
#   f35-release
ARG git_branch

# The `copr_repo` arg will set Anaconda daily builds copr repository.
# possible values:
#   @rhinstaller/Anaconda
#   @rhinstaller/Anaconda-devel
ARG copr_repo
LABEL maintainer=anaconda-devel@lists.fedoraproject.org

# On ELN, BaseOS+AppStream don't have all our build dependencies; this provides the "Everything" compose
COPY ["eln.repo", "/etc/yum.repos.d"]

# The anaconda.spec.in is in the repository root. This file will be copied automatically here if
# the build is invoked by Makefile.
COPY ["anaconda.spec.in", "/root/"]

# Prepare environment and install build dependencies
RUN set -ex; \
  if grep -q VARIANT.*eln /etc/os-release; then sed -i 's/enabled=0/enabled=1/' /etc/yum.repos.d/eln.repo; fi; \
  dnf install -y \
  'dnf-command(copr)'; \
  # Enable COPR repositories
  if ! grep -q VARIANT.*eln /etc/os-release; then \
    BRANCH="${git_branch}"; \
    if [ $BRANCH == "master" ]; then \
      BRANCH="rawhide"; \
    fi; \
    BRANCH=${BRANCH%%-*}; \
    BRANCH=${BRANCH#f}; \
    dnf copr enable -y ${copr_repo} fedora-${BRANCH}-x86_64; \
    dnf copr enable -y @storage/blivet-daily fedora-${BRANCH}-x86_64; \
    dnf -y install cppcheck; \
  else \
    dnf copr enable -y ${copr_repo} fedora-eln-x86_64; \
  fi; \
  # Update the base container packages
  dnf update -y; \
  # Install rest of the dependencies
  dnf install -y \
  /usr/bin/xargs \
  nodejs \
  rpm-build \
  git \
  bzip2 \
  rpm-ostree \
  python3-pip \
  # Need to have restorecon for the tests execution
  policycoreutils \
  ShellCheck; \
  # Install Anaconda dependencies
  cat /root/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | xargs -d '\n' dnf install -y; \
  dnf clean all

RUN pip install --no-cache-dir --upgrade pip; \
  pip install --no-cache-dir \
  pocketlint \
  coverage \
  pycodestyle \
  dogtail \
  rpmfluff \
  freezegun \
  pytest

RUN mkdir /anaconda

WORKDIR /anaconda

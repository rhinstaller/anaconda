# This container is used for runing Anaconda unit tests in the controlled environment.
# To find out how to build this container please look on the ./tests/README.rst file.

# The `image` arg will set base image for the build.
# possible values:
#   registry.fedoraproject.org/fedora:38
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
#   fedora-38
ARG git_branch

# The `copr_repo` arg will set Anaconda daily builds copr repository.
# possible values:
#   @rhinstaller/Anaconda
#   @rhinstaller/Anaconda-devel
ARG copr_repo
LABEL maintainer=anaconda-devel@lists.fedoraproject.org

# The anaconda.spec.in is in the repository root. This file will be copied automatically here if
# the build is invoked by Makefile.
COPY ["anaconda.spec.in", "requirements.txt", "/root/"]

# Prepare environment and install build dependencies
RUN set -ex; \
  dnf install -y \
  'dnf5-command(copr)'; \
  # Enable COPR repositories
  if ! grep -q VARIANT.*eln /etc/os-release; then \
    BRANCH="${git_branch}"; \
    if [ $BRANCH == "master" ]; then \
      BRANCH="rawhide"; \
    fi; \
    BRANCH=${BRANCH#fedora-}; \
    dnf copr enable -y ${copr_repo} fedora-${BRANCH}-x86_64; \
    dnf copr enable -y @storage/blivet-daily fedora-${BRANCH}-x86_64; \
    dnf copr enable -y @storage/udisks-daily fedora-${BRANCH}-x86_64; \
  else \
    dnf copr enable -y ${copr_repo} fedora-eln-x86_64; \
  fi; \
  # Update the base container packages
  dnf update -y; \
  # Install rest of the dependencies
  dnf install -y \
  /usr/bin/xargs \
  rpm-build \
  git \
  bzip2 \
  rpm-ostree \
  python3-pip \
  rsync \
  # Need to have restorecon for the tests execution
  policycoreutils; \
  # Install non-ELN dependencies
  if ! grep -q VARIANT.*eln /etc/os-release; then \
    dnf -y install \
    cppcheck \
    ShellCheck; \
  fi; \
  # Install Anaconda dependencies
  cat /root/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  # xisxwayland is specifically excluded because it isn't in ELN
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | grep -v xisxwayland | xargs -d '\n' dnf install -y; \
  dnf clean all

RUN pip install --no-cache-dir --upgrade pip; \
  pip install --no-cache-dir -r /root/requirements.txt

RUN mkdir /anaconda

WORKDIR /anaconda

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
# Add our own repositories
COPY *.repo /etc/yum.repos.d/
# Enable CRB repository
RUN set -ex; \
  dnf install -y dnf-plugins-core; \
  dnf config-manager --enable crb; \
  dnf remove -y dnf-plugins-core

# Prepare environment and install build dependencies
RUN set -ex; \
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
  # cppcheck \
  # ShellCheck; \
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
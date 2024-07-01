# This container is used for runing Anaconda RPM tests in the controlled environment.
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
ARG copr_repo=@rhinstaller/Anaconda
LABEL maintainer=anaconda-devel@lists.fedoraproject.org

# Add development repositories instead of the production ones
# We need development repositories to get our dependencies sooner
RUN rm -f /etc/yum.repos.d/*.repo
COPY ["anaconda-centos.repo", "/etc/yum.repos.d/"]

# The anaconda.spec.in is in the repository root. This file will be copied automatically here if
# the build is invoked by Makefile.
COPY ["anaconda.spec.in", "requirements.txt", "/root/"]

# Prepare environment and install build dependencies
RUN set -ex; \
  dnf update -y; \
  # Install dependencies
  dnf install -y \
  git \
  curl \
  /usr/bin/xargs \
  rsync \
  python3-pip \
  rpm-build; \
  cat /root/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  dnf clean all; \
  mkdir /anaconda

RUN pip install --no-cache-dir --upgrade pip; \
  pip install --no-cache-dir -r /root/requirements.txt

WORKDIR /anaconda

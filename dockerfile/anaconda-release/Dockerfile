# Dockerfile to enable releases of Anaconda for RHEL independently of the host system.
#
# This will be based on our existing anaconda-rpm container because it has all the dependencies
# required to build Anaconda.

ARG image
FROM ${image}
LABEL maintainer=anaconda-list@redhat.com

# Add development repositories instead of the production ones
# We need development repositories to get our dependencies sooner
RUN rm -f /etc/yum.repos.d/*.repo
COPY ["anaconda-centos.repo", "/etc/yum.repos.d/"]

# Add missing dependencies required to do the build.
RUN set -e; \
  dnf update -y; \
  dnf install -y \
  git \
  python3-pip; \
  dnf clean all;

RUN pip3 install --no-cache-dir --upgrade pip; \
    pip3 install --no-cache-dir \
    pocketlint

WORKDIR /anaconda

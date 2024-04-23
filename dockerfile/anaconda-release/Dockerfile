# Dockerfile to enable releases of Anaconda for RHEL independently of the host system.
#
# This will be based on our existing anaconda-rpm container because it has all the dependencies
# required to build Anaconda.

FROM quay.io/rhinstaller/anaconda-rpm:rhel-9
LABEL maintainer=anaconda-list@redhat.com

# Add missing dependencies required to do the build.
RUN set -e; \
  dnf update -y; \
  dnf install -y git; \
  dnf clean all;

RUN pip3 install --no-cache-dir --upgrade pip; \
  pip3 install --no-cache-dir \
  pocketlint

WORKDIR /anaconda

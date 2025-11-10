# Dockerfile to enable releases of Anaconda for RHEL independently of the host system.
#
# This will be based on our existing anaconda-rpm container because it has all the dependencies
# required to build Anaconda.

ARG image
FROM ${image}
LABEL maintainer=anaconda-list@redhat.com

# Add missing dependencies required to do the build.
RUN set -e; \
  dnf update -y; \
  # disable fedora-cisco repository otherwise freerdp will depend on openh264 from fedora-cisco
  # if fedora-cisco is not enabled it will fallback to stub library in main repository which is
  # what we want
  if ! grep -q VARIANT.*eln /etc/os-release; then \
    # disable fedora-cisco repository otherwise freerdp will depend on openh264 from fedora-cisco
    # if fedora-cisco is not enabled it will fallback to stub library in main repository which is
    # what we want
    sed -i 's/enabled=1/enabled=0/' /etc/yum.repos.d/fedora-cisco-openh264.repo; \
  fi; \
  dnf install -y \
  git \
  python3-pip; \
  dnf clean all;

RUN pip3 install --no-cache-dir --upgrade pip; \
    pip3 install --no-cache-dir \
    pocketlint

WORKDIR /anaconda

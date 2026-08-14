# Dockerfile to enable releases of Anaconda for RHEL independently of the host system.
#
# This will be based on our existing anaconda-rpm container because it has all the dependencies
# required to build Anaconda.

ARG image
FROM ${image}
LABEL maintainer=anaconda-list@redhat.com

# FIXME: workaround — disable the fedora-cisco-openh264 repo so that freerdp falls back to
# the stub openh264 in the main Fedora repo and dnf does not hit GPG key failures on it.
# Remove this once the base image no longer ships the cisco repo enabled by default.
RUN mkdir -p /etc/dnf/repos.override.d && \
    printf '[fedora-cisco-openh264]\nenabled=0\n' > /etc/dnf/repos.override.d/disable-cisco-openh264.repo

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

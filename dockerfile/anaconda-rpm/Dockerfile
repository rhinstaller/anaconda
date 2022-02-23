FROM registry.access.redhat.com/ubi8:latest
LABEL maintainer=anaconda-list@redhat.com

# Enable our repositories (RHEL 8 and overlays)
RUN rm /etc/yum.repos.d/*.repo
COPY *.repo /etc/yum.repos.d/

# Prepare environment and install build dependencies
RUN set -e; \
  dnf update -y; \
  dnf install -y \
  curl \
  /usr/bin/xargs \
  rpm-build; \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/rhel-8/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  dnf clean all; \
  mkdir /anaconda

WORKDIR /anaconda

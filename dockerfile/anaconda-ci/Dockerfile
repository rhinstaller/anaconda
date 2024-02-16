FROM registry.access.redhat.com/ubi8:latest
LABEL maintainer=anaconda-list@redhat.com

# Enable our repositories (RHEL 8 and overlays)
RUN rm /etc/yum.repos.d/*.repo
COPY *.repo /etc/yum.repos.d/

# Prepare environment and install build dependencies
RUN echo dnf update -y && \
  dnf install -y \
  curl \
  /usr/bin/xargs \
  rpm-build \
  e2fsprogs \
  # the krb5-config binary is required for copr pip installation
  krb5-devel \
  git \
  bzip2 \
  cppcheck \
  libicu \
  lttng-ust \
  rpm-ostree \
  patch \
  pykickstart \
  python3-pip \
  python3-lxml \
  policycoreutils \
  python3-gobject-base \
  python3-pip && \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/rhel-8/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec && \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y && \
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | xargs -d '\n' dnf install -y && \
  dnf clean all

RUN pip-3.6 install \
  "pylint==2.5.3" \
  "astroid==2.4.2" \
  "pocketlint==0.24" \
  copr \
  coverage \
  pycodestyle \
  dogtail \
  nose-testconfig \
  rpmfluff \
  jinja2 \
  pyyaml

# see https://github.com/martinpitt/anaconda/settings/actions/add-new-runner
RUN mkdir actions-runner && cd actions-runner && \
  URL_BASE=https://github.com/actions/runner/releases && \
  LATEST_VER=$(basename $(curl -Ls -o /dev/null -w '%{url_effective}' $URL_BASE/latest)) && \
  curl -L "$URL_BASE/download/$LATEST_VER/actions-runner-linux-x64-${LATEST_VER#v}.tar.gz" | tar xvz

RUN mkdir /anaconda

WORKDIR /anaconda

COPY ["github-action-run-once", "/"]

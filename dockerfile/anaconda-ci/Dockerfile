FROM fedora:rawhide
ARG eln=
LABEL maintainer=anaconda-list@redhat.com

# HACK: there is no official fedora-eln container image yet, so cross-grade from rawhide
COPY ["eln.repo", "/etc/yum.repos.d"]

# Prepare environment and install build dependencies
RUN set -e; \
  if [ -n "$eln" ]; then \
      sed -i 's/enabled=0/enabled=1/' /etc/yum.repos.d/eln.repo; \
      dnf install -y --allowerasing fedora-release-eln; \
  fi; \
  dnf distro-sync -y; \
  if [ -n "$eln" ]; then \
      rm -f /etc/yum.repos.d/fedora*; \
      if noneln=$(rpm -qa | grep -Ev '\.eln|^gpg-pubkey'); then \
          echo "ERROR: Non-ELN packages: $noneln" >&2; exit 1; \
      fi; \
  fi; \
  dnf install -y \
  'dnf-command(copr)' \
  curl \
  /usr/bin/xargs \
  rpm-build \
  e2fsprogs \
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
  python3-pip; \
  if [ -z "$eln" ]; then dnf copr enable -y @rhinstaller/Anaconda; dnf copr enable -y @storage/blivet-daily; fi; \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/master/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | xargs -d '\n' dnf install -y; \
  dnf clean all

RUN pip install \
  pocketlint \
  coverage \
  pycodestyle \
  dogtail \
  nose-testconfig \
  rpmfluff

# HACK: Apply fix from https://github.com/PyCQA/astroid/pull/847 to avoid
# excessive memory usage, until astroid > 2.4.2 gets released
RUN curl https://github.com/PyCQA/astroid/commit/d62349a424c549b4634c90e471c9f876b99edfeb.patch | patch /usr/local/lib/python3*/site-packages/astroid/manager.py

# see https://github.com/martinpitt/anaconda/settings/actions/add-new-runner
RUN mkdir actions-runner && cd actions-runner && \
  URL_BASE=https://github.com/actions/runner/releases && \
  LATEST_VER=$(basename $(curl -Ls -o /dev/null -w '%{url_effective}' $URL_BASE/latest)) && \
  curl -L "$URL_BASE/download/$LATEST_VER/actions-runner-linux-x64-${LATEST_VER#v}.tar.gz" | tar xvz

RUN mkdir /anaconda

WORKDIR /anaconda

COPY ["github-action-run-once", "/"]

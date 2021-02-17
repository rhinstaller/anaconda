ARG image=registry.fedoraproject.org/fedora:rawhide
FROM ${image}
# FROM starts a new build stage with new ARGs. Put any ARGs after FROM unless required by the FROM itself.
# see https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact
ARG git_branch=master
ARG copr_repo=@rhinstaller/Anaconda
LABEL maintainer=anaconda-list@redhat.com

# On ELN, BaseOS+AppStream don't have all our build dependencies; this provides the "Everything" compose
COPY ["eln.repo", "/etc/yum.repos.d"]

# Prepare environment and install build dependencies
RUN set -e; \
  if grep -q VARIANT.*eln /etc/os-release; then sed -i 's/enabled=0/enabled=1/' /etc/yum.repos.d/eln.repo; fi; \
  dnf update -y; \
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
  if ! grep -q VARIANT.*eln /etc/os-release; then dnf copr enable -y ${copr_repo}; dnf copr enable -y @storage/blivet-daily; fi; \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/${git_branch}/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | xargs -d '\n' dnf install -y; \
  dnf clean all

RUN pip install \
  pocketlint \
  coverage \
  pycodestyle \
  dogtail \
  nose-testconfig \
  nose \
  rpmfluff

# see https://github.com/martinpitt/anaconda/settings/actions/add-new-runner
RUN mkdir actions-runner && cd actions-runner && \
  URL_BASE=https://github.com/actions/runner/releases && \
  LATEST_VER=$(basename $(curl -Ls -o /dev/null -w '%{url_effective}' $URL_BASE/latest)) && \
  curl -L "$URL_BASE/download/$LATEST_VER/actions-runner-linux-x64-${LATEST_VER#v}.tar.gz" | tar xvz

RUN mkdir /anaconda

WORKDIR /anaconda

COPY ["github-action-run-once", "/"]

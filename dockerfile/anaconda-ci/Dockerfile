ARG image
FROM ${image}
# FROM starts a new build stage with new ARGs. Put any ARGs after FROM unless required by the FROM itself.
# see https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact
ARG git_branch
ARG copr_repo
LABEL maintainer=anaconda-devel@lists.fedoraproject.org

# Enable CRB repository
RUN set -ex; \
  dnf install -y dnf-plugins-core; \
  dnf config-manager --enable crb; \
  dnf remove -y dnf-plugins-core


# Prepare environment and install build dependencies
RUN set -e; \
  dnf update -y; \
  dnf install -y \
  curl-minimal \
  /usr/bin/xargs \
  rpm-build \
  e2fsprogs \
  git \
  bzip2 \
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
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/${git_branch}/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | xargs -d '\n' dnf install -y; \
  dnf clean all

RUN pip install \
  "pylint==2.8.3" \
  "astroid==2.5.6" \
  "pocketlint==0.24" \
  coverage \
  pycodestyle \
  dogtail \
  rpmfluff \
  pytest \
  jinja2 \
  pyyaml

RUN mkdir /anaconda

WORKDIR /anaconda

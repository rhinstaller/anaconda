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
  python3-pip \
  /usr/bin/xargs \
  rpm-build; \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/${git_branch}/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  dnf clean all; \
  mkdir /anaconda

WORKDIR /anaconda

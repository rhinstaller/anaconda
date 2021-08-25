ARG image=registry.fedoraproject.org/fedora:35
FROM ${image}
# FROM starts a new build stage with new ARGs. Put any ARGs after FROM unless required by the FROM itself.
# see https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact
ARG git_branch=f35-devel
ARG copr_repo=@rhinstaller/Anaconda-devel
LABEL maintainer=anaconda-list@redhat.com

# On ELN, BaseOS+AppStream don't have all our build dependencies; this provides the "Everything" compose
COPY ["eln.repo", "/etc/yum.repos.d"]

# Prepare environment and install build dependencies
RUN set -ex; \
  if grep -q VARIANT.*eln /etc/os-release; then sed -i 's/enabled=0/enabled=1/' /etc/yum.repos.d/eln.repo; fi; \
  dnf update -y; \
  dnf install -y \
  'dnf-command(copr)' \
  curl \
  python3-pip \
  /usr/bin/xargs \
  rpm-build; \
  if ! grep -q VARIANT.*eln /etc/os-release; then \
    BRANCH="${git_branch}"; \
    if [ $BRANCH == "master" ]; then \
      BRANCH="rawhide"; \
    fi; \
    dnf copr enable -y ${copr_repo} fedora-${BRANCH%%-*}-x86_64; \
    dnf copr enable -y @storage/blivet-daily fedora-${BRANCH%%-*}-x86_64; \
  else \
    dnf copr enable -y ${copr_repo} fedora-eln-x86_64; \
  fi; \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/${git_branch}/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec; \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y; \
  dnf clean all; \
  mkdir /anaconda

WORKDIR /anaconda

FROM fedora:rawhide
LABEL maintainer=anaconda-list@redhat.com

# Prepare environment and install build dependencies
RUN dnf update -y && \
  dnf install -y \
  'dnf-command(copr)' \
  curl \
  /usr/bin/xargs \
  rpm-build \
  e2fsprogs \
  git \
  bzip2 \
  cppcheck \
  rpm-ostree \
  pykickstart \
  python3-pip \
  python3-lxml \
  policycoreutils \
  python3-gobject-base \
  python3-pip && \
  dnf copr enable -y @rhinstaller/Anaconda && \
  dnf copr enable -y @storage/blivet-daily && \
  curl -L https://raw.githubusercontent.com/rhinstaller/anaconda/master/anaconda.spec.in | sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' > /tmp/anaconda.spec && \
  rpmspec -q --buildrequires /tmp/anaconda.spec | xargs -d '\n' dnf install -y && \
  rpmspec -q --requires /tmp/anaconda.spec | grep -v anaconda | xargs -d '\n' dnf install -y && \
  dnf clean all

RUN pip install \
  pocketlint \
  coverage \
  pycodestyle \
  dogtail \
  nose-testconfig \
  rpmfluff

RUN mkdir /anaconda

WORKDIR /anaconda
CMD ./autogen.sh && ./configure && make && make ci

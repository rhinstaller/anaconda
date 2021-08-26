# Dockerfile to build boot.iso with Anaconda from the repository.
# This container has to be started as --privileged and with precreated loop devices otherwise
# lorax won't work correctly.
#
# Execution example:
#
# make -f ./Makefile.am container-rpms-scratch # Create Anaconda RPM in `pwd`/result/... directory.
# sudo make -f ./Makefile.am anaconda-iso-creator-build
#
# # pre-create loop devices because the container namespacing of /dev devices
# sudo mknod -m 0660 /dev/loop0 b 7 0  2> /dev/null || true
# sudo mknod -m 0660 /dev/loop1 b 7 1  2> /dev/null || true
#
# # /var/tmp tmpfs speeds up lorax and avoids https://bugzilla.redhat.com/show_bug.cgi?id=1906364
# sudo podman run -i --rm --privileged --tmpfs /var/tmp:rw,mode=1777 -v `pwd`/result/build/01-rpm-build:/anaconda-rpms:ro -v `pwd`/output-dir:/images:z quay.io/rhinstaller/anaconda-iso-creator:master
#
# note:
# - add `--network=slirp4netns` if you need to share network with host computer to reach
#   repositories (VPN for example)
#

ARG image=registry.fedoraproject.org/fedora:rawhide
FROM ${image}
# FROM starts a new build stage with new ARGs. Put any ARGs after FROM unless required by the FROM itself.
# see https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact
LABEL maintainer=anaconda-list@redhat.com

# Prepare environment and install build dependencies
RUN set -ex; \
  dnf update -y; \
  dnf install -y \
  createrepo_c \
  lorax; \
  dnf clean all

COPY ["lorax-build", "/"]

RUN mkdir /lorax && \
  mkdir /anaconda-rpms

WORKDIR /lorax

ENTRYPOINT /lorax-build

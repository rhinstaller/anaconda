# KIWI runner image for building Fedora Workstation Live ISO.
# Uses official fedora-kiwi-descriptions from https://pagure.io/fedora-kiwi-descriptions
# Branch is selected based on CI_TAG (fedora-rawhide -> rawhide, fedora-43 -> f43, etc.)
#
# Usage:
#   make -f ./Makefile.am container-rpms-scratch
#   sudo make -f ./Makefile.am anaconda-kiwi-live-iso-creator-build
#   sudo make -f ./Makefile.am container-kiwi-live-iso-build
ARG image
FROM ${image}
LABEL maintainer=anaconda-devel@lists.fedoraproject.org

ARG CI_TAG=fedora-rawhide
ENV CI_TAG=${CI_TAG}

RUN set -ex; \
  dnf -y update && \
  dnf -y install \
    kiwi-cli \
    kiwi-systemdeps \
    kiwi-boxed-plugin \
    distribution-gpg-keys \
    createrepo_c \
    git && \
  dnf clean all

RUN mkdir -p /work /images /anaconda-rpms /repos
VOLUME ["/var/cache/dnf"]

COPY kiwi-build /usr/local/bin/kiwi-build
RUN chmod +x /usr/local/bin/kiwi-build

# Disable SELinux in build container as per KIWI documentation:
# https://documentation.suse.com/appliance/kiwi-9/html/kiwi/troubleshooting.html#host-security-settings-conflicts-with-kiwi
# SELinux policies conflict with KIWI's requirement to access a wide range of services
# (creating package databases, device nodes, filesystems, partitions, etc.)
RUN if [ -e /etc/selinux/config ]; then \
      sed -i 's/^SELINUX=.*/SELINUX=disabled/' /etc/selinux/config || \
      echo "SELINUX=disabled" >> /etc/selinux/config; \
    fi

WORKDIR /work
ENTRYPOINT ["/usr/local/bin/kiwi-build"]

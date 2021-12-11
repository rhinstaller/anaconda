# This container is used for building Anaconda RPM files on COPR.

ARG image=quay.io/rhinstaller/anaconda-ci:master
FROM ${image}
# FROM starts a new build stage with new ARGs. Put any ARGs after FROM unless required by the FROM itself.
# see https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact

LABEL maintainer=anaconda-devel@lists.fedoraproject.org

# Install build dependencies
RUN set -e; \
  dnf install -y python3-copr git; \
  git clone --depth 1 https://github.com/vojtechtrefny/copr-builder.git /copr-builder

COPY ["copr-builder-rhel.conf", "/copr-builder"]

# Add certificates needed to connect to the COPR
RUN set -e; \
  curl -k https://password.corp.redhat.com/cacert.crt -o /etc/pki/ca-trust/source/anchors/Red_Hat_IS_CA.crt; \
  curl -k https://password.corp.redhat.com/RH-IT-Root-CA.crt -o /etc/pki/ca-trust/source/anchors/Red_Hat_IT_Root_CA.crt; \
  curl -k https://engineering.redhat.com/Eng-CA.crt -o /etc/pki/ca-trust/source/anchors/Eng_Ops_CA.crt; \
  curl -k https://password.corp.redhat.com/pki-ca-chain.crt -o /etc/pki/ca-trust/source/anchors/PKI_CA_Chain.crt; \
  ln -sf /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem /etc/pki/tls/certs/ca-bundle.crt; \
  update-ca-trust

WORKDIR /

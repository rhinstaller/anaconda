#!/bin/bash
#
# This script installs the additional dependencies needed for the webui only.
# It is expected that anaconda main dependencies are already installed with
# https://github.com/rhinstaller/anaconda/blob/master/scripts/testing/install_dependencies.sh
#
# You can also pass any additional parameters for dnf. To make installation
# non-interactive you can call:
#
#    $ sudo ./scripts/testings/install_webui_only_dependencies.sh -y

set -eu

# Cockpit tests dependencies - taken from https://github.com/cockpit-project/cockpituous/blob/main/tasks/Dockerfile
# and some additional Web UI tests dependencies - these are specific to anaconda Web UI tests and not listed in cockpit
# shellcheck disable=SC2068
dnf install $@ \
    chromium-headless \
    firefox \
    npm \
    qemu-img \
    qemu-kvm-core \
    virt-install

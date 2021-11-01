#!/bin/bash
#
# Anaconda has plenty of dependencies and because of that it's hard to set
# environment to with Anaconda properly.
# Run this script to install all the required dependencies for the autotools to be
# able to call make commands. This will enable you to test anaconda more easily.
#
# To avoid messing your system feel free to use `toolbox` in fedora so all the
# dependencies will be installed to the container instead of your system.
# The toolbox package is in standard Fedora repository.
#
# For toolbox use case run:
#
#   $ toolbox create
#   $ toolbox enter
#   $ sudo ./scripts/testing/install_dependencies.sh
#
#
# For direct host installation run:
#
#   $ sudo ./scripts/testing/install_dependencies.sh
#
#
# You can also pass any additional parameters for dnf. To make installation
# non-interactive you can call:
#
#   $ sudo ./scripts/testing/install_dependencies.sh -y

set -eu

dnf install "$@" rpm-build /usr/bin/xargs

TEMP=$(mktemp /tmp/anaconda.spec.XXXXXXX)

# remove all problematic pieces from anaconda spec to be able to get dependencies
sed 's/@PACKAGE_VERSION@/0/; s/@PACKAGE_RELEASE@/0/; s/%{__python3}/python3/' ./anaconda.spec.in > "$TEMP"

# get all build requires dependencies from the spec file and strip out version
# version could be problematic because of fedora version you are running and
# they are mostly not important for automake
rpmspec -q --buildrequires "$TEMP" | sed 's/>=.*$//' | xargs -d '\n' dnf install "$@"

# clean up the temp file
rm "$TEMP"

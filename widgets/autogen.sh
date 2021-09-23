#!/bin/bash -e

autoreconf -vfi

# Remove the old symlink if present
if [ -h src/gettext.h ] ; then rm src/gettext.h ; fi
cp -f /usr/share/gettext/gettext.h src

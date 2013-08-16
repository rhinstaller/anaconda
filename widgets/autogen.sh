#!/bin/bash -e
[ -d m4 ] || mkdir m4
libtoolize --copy --force
gtkdocize --copy
aclocal -I m4
autoconf
autoheader --force
automake --foreign --add-missing --copy
rm -rf autom4te.cache

# Remove the old symlink if present
if [ -h src/gettext.h ] ; then rm src/gettext.h ; fi
cp -f /usr/share/gettext/gettext.h src

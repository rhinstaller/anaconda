#!/bin/bash
aclocal -I m4
libtoolize --copy --force
gtkdocize
autoconf
autoheader
touch config.h.in
automake --foreign --add-missing --copy
rm -rf autom4te.cache
ln -sf /usr/share/gettext/gettext.h src

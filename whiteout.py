#
# whiteout.py - dependency whiteout setup
#
# Copyright 2002  Red Hat, Inc.
#

import rpm404 as rpm

whiteout="""
	pango-gtkbeta-devel>pango-gtkbeta\
	XFree86>Mesa			\
	compat-glibc>db2		\
	compat-glibc>db1		\
	pam>initscripts			\
	initscripts>sysklogd            \
	arts>kdelibs-sound              \
	libgnomeprint15>gnome-print	\
	nautilus>nautilus-mozilla	\
	tcl>postgresql-tcl              \
	libtermcap>bash			\
	modutils>vixie-cron		\
	ypbind>yp-tools			\
	ghostscript-fonts>ghostscript	\
        usermode>util-linux             \
        control-center>xscreensaver     \
        kdemultimedia-arts>kdemultimedia-libs \
        initscripts>util-linux          \
        XFree86-libs>XFree86-Mesa-libGL \
        mysql>perl-DBD-MySQL            \
        ghostscript>gimp-print          \
        bind>bind-utils
"""

rpm.addMacro("_dependency_whiteout", whiteout)

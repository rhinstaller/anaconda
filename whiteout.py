#
# whiteout.py - dependency whiteout setup
#
# Copyright 2002  Red Hat, Inc.
#

import rpm

# set DB_PRIVATE to make rpm happy...  do it in here since we include
# this with all of the useful rpm bits
# rpm.addMacro("__dbi_cdb", "create private")

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
        bind>bind-utils                 \
        perl>mod_perl                   \
        perl>perl-Filter                \
        coreutils>pam                   \
        perl>mrtg                       \
        perl-Date-Calc>perl-Bit-Vector  \
        glibc-debug>glibc-devel
"""

rpm.addMacro("_dependency_whiteout", whiteout)

#
# whiteout.py - dependency whiteout setup
#
# Copyright 2002-2004  Red Hat, Inc.
#

import os
import rhpl.arch
from flags import flags

import logging
log = logging.getLogger("anaconda")

whiteout="""
	pango-gtkbeta-devel>pango-gtkbeta\
	XFree86>Mesa			\
        xorg-x11>Mesa			\
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
        xorg-x11-libs>xorg-x11-Mesa-libGL \
        mysql>perl-DBD-MySQL            \
        ghostscript>gimp-print          \
        bind>bind-utils                 \
        perl>mod_perl                   \
        perl>perl-Filter                \
        coreutils>pam                   \
        perl>mrtg                       \
        perl-Date-Calc>perl-Bit-Vector  \
        glibc-debug>glibc-devel \
	xinitrc>XFree86 \
        xinitrc>xorg-x11 \
	xemacs>apel-xemacs \
	gimp>gimp-print-plugin \
        redhat-lsb>redhat-lsb \
        info>ncurses \
        aspell>aspell-en \
        dbus>dbus-glib \
        xemacs>xemacs-sumo \
        ncurses>gpm \
        cyrus-sasl>openldap \
        lvm2>kernel \
        initscripts>kernel \
        initscripts>kernel-smp \
        httpd>httpd-suexec \
        php>php-pear \
        gnome-python2>gnome-python2-bonobo \
        openoffice.org-libs>openoffice.org \
        gtk+>gdk-pixbuf \
        nautilus>nautilus-cd-burner \
        hicolor-icon-theme>gtk2 \
        gtk2>scim-libs
"""

whitetup = map(lambda x: (x.split(">")[0], x.split(">")[1]), whiteout.split())

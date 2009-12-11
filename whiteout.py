#
# whiteout.py - dependency whiteout setup
#
# Copyright 2002-2004  Red Hat, Inc.
#

import os
import rpm
import rhpl.arch
from flags import flags

import logging
log = logging.getLogger("anaconda")

# set DB_PRIVATE to make rpm happy...  do it in here since we include
# this with all of the useful rpm bits
#rpm.addMacro("__dbi_cdb", "create private mpool mp_mmapsize=16Mb mp_size=1Mb")

## assuming that SELinux is set up, tell rpm where to pull file contexts from
#if flags.selinux:
#    for dir in ("/tmp/updates", "/mnt/source/RHupdates",
#                "/etc/selinux/targeted/contexts/files",
#                "/etc/security/selinux/src/policy/file_contexts",
#                "/etc/security/selinux"):
#        fn = "%s/file_contexts" %(dir,)
#        if os.access(fn, os.R_OK):
#            break
#    rpm.addMacro("__file_context_path", fn)
#    log.info("setting file_context_path to %s" %(fn,))    
#else:
#    log.info("setting file_context_path to nil")
#    rpm.addMacro("__file_context_path", "%{nil}")
#
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
	ghostscript>ghostscript-fonts	\
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
        nautilus>nautilus-cd-burner
"""

whitetup = map(lambda x: (x.split(">")[0], x.split(">")[1]), whiteout.split())

#rpm.addMacro("_dependency_whiteout", whiteout)

# ts coloring, more hacks to workaround #92285
#if (rhpl.arch.canonArch.startswith("ppc64") or
#    rhpl.arch.canonArch in ("s390x", "sparc64", "x86_64", "ia64")):
#    rpm.addMacro("_transaction_color", "3")

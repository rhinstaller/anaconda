# loader/Makefile.am for anaconda
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: David Cantrell <dcantrell@redhat.com>

bootdir            = $(libdir)/$(PACKAGE_NAME)
shareddir          = $(datadir)/$(PACKAGE_NAME)

boot_PROGRAMS      = loader
shared_DATA        = loader.tr
dist_shared_DATA   = unicode-linedraw-chars.txt
noinst_PROGRAMS    = mkctype dirbrowser
noinst_DATA        = ctype.c
noinst_HEADERS     = *.h

if IS_S390
boot_PROGRAMS      += shutdown
dist_shared_SCRIPTS  = linuxrc.s390
else
boot_PROGRAMS       += init
endif

if IS_KEYMAPS_OVERRIDE_ARCH
keymapsdir         = $(datadir)/$(PACKAGE_NAME)
keymaps_DATA       = keymaps-override-$(ARCH)
endif

COMMON_CFLAGS      = -DUSE_LOGDEV -DVERSION='"$(PACKAGE_VERSION)"'

loader_CFLAGS      = $(COMMON_CFLAGS) $(GLIB_CFLAGS) $(LIBNM_GLIB_CFLAGS) \
                     $(LIBCURL_CFLAGS) $(IPV6_CFLAGS) $(LIBARCHIVE_CFLAGS) \
                     $(RPM_CFLAGS) -DINCLUDE_LOCAL -DINCLUDE_NETWORK
loader_LDADD       = $(NEWT_LIBS) $(GLIB_LIBS) $(LIBNL_LIBS) \
                     $(LIBNM_GLIB_LIBS) $(CHECKISOMD5_LIBS) \
                     $(LIBCURL_LIBS) $(LIBARCHIVE_LIBS) $(RPM_LIBS) \
                     $(ISCSI_LIBS) $(top_srcdir)/isys/libisys.la -lm
loader_SOURCES     = loader.c copy.c moduleinfo.c loadermisc.c \
                     modules.c windows.c lang.c kbd.c driverdisk.c \
                     selinux.c mediacheck.c kickstart.c driverselect.c \
                     getparts.c dirbrowser.c fwloader.c ibft.c hardware.c \
                     method.c cdinstall.c hdinstall.c nfsinstall.c \
                     urlinstall.c net.c urls.c telnet.c telnetd.c \
                     rpmextract.c

init_CFLAGS        = $(COMMON_CFLAGS) $(GLIB_CFLAGS)
init_LDADD	   = $(GLIB_LIBS)
init_SOURCES       = init.c undomounts.c shutdown.c copy.c

shutdown_CFLAGS    = $(COMMON_CFLAGS) -DAS_SHUTDOWN=1
shutdown_SOURCES   = shutdown.c undomounts.c

mkctype_CFLAGS     = $(COMMON_CFLAGS)
mkctype_SOURCES    = mkctype.c

dirbrowser_CFLAGS  = $(COMMON_CFLAGS) -DSTANDALONE
dirbrowser_LDADD   = $(NEWT_LIBS)
dirbrowser_SOURCES = dirbrowser.c

EXTRA_DIST = simplemot keymaps-*

CLEANFILES = keymaps-override-$(ARCH) ctype.c tr/*.tr

MAINTAINERCLEANFILES = Makefile.in

sed_verbose = $(sed_verbose_$(V))
sed_verbose_ = $(sed_verbose_$(AM_DEFAULT_VERBOSITY))
sed_verbose_0 = @echo "  SED    "$@;

cp_verbose = $(cp_verbose_$(V))
cp_verbose_ = $(cp_verbose_$(AM_DEFAULT_VERBOSITY))
cp_verbose_0 = @echo "  CP     "$@;

mkctype_verbose = $(mkctype_verbose_$(V))
mkctype_verbose_ = $(mkctype_verbose_$(AM_DEFAULT_VERBOSITY))
mkctype_verbose_0 = @echo "  MAKE   "$@;

msgmerge_verbose = $(msgmerge_verbose_$(V))
msgmerge_verbose_ = $(msgmerge_verbose_$(AM_DEFAULT_VERBOSITY))
msgmerge_verbose_0 = echo "  MERGE  "$${lang}.po;

xgettext_verbose = $(xgettext_verbose_$(V))
xgettext_verbose_ = $(xgettext_verbose_$(AM_DEFAULT_VERBOSITY))
xgettext_verbose_0 = @echo "  GETTXT "$@;

keymaps-override-$(ARCH): keymaps-$(ARCH)
	$(cp_verbose)cp -p $< $@

ctype.c: mkctype
	$(mkctype_verbose)./mkctype > ctype.c

loader.tr: $(top_srcdir)/lang-table loader.po
	@LANGS="`cut -f 2 $(top_srcdir)/lang-table | egrep -v '(^en$$)'`" ; \
	if [ ! -d tr ]; then \
		mkdir -p tr ; \
	fi ; \
	for lang in $$LANGS ; do \
		$(msgmerge_verbose)msgmerge -q $(top_srcdir)/po/$$lang.po loader.po | msgconv -t utf-8 | ./simplemot > tr/$$lang.tr ; \
	done ; \
	(cd tr ; ls -1 *.tr | cpio --quiet -Hcrc -o | gzip -9) > $@

loader.po:
	$(xgettext_verbose)xgettext --default-domain=loader --add-comments \
		--keyword=_ --keyword=N_ *.c
	$(sed_verbose)sed -i 's/charset=CHARSET/charset=UTF-8/' $@

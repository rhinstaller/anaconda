# Makefile.am for anaconda
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

ACLOCAL_AMFLAGS = -I m4

SUBDIRS = isys po loader booty storage textw utils scripts bootdisk \
          installclasses iw command-stubs ui docs pixmaps tests fonts \
          gptsync liveinst

EXTRA_DIST = config.rpath COPYING pychecker-false-positives \
             pycheckrc-for-anaconda runpychecker.sh lang-table \
             anaconda.spec.in

MAINTAINERCLEANFILES = Makefile.in config.guess config.h.in config.sub \
                       depcomp install-sh ltmain.sh missing ABOUT-NLS \
                       INSTALL aclocal.m4 configure *.pyc py-compile

CLEANFILES = *~ lang-names anaconda.spec

MOSTLYCLEANDIRS = m4

dist_noinst_DATA      = $(PACKAGE_NAME).spec

bin_PROGRAMS          = mini-wm
dist_sbin_SCRIPTS     = anaconda

mini_wm_CFLAGS        = $(X11_CFLAGS) $(XCOMPOSITE_CFLAGS) $(GTK_X11_CFLAGS)
mini_wm_LDFLAGS       = $(X11_LIBS) $(XCOMPOSITE_LIBS) $(GTK_X11_LIBS)
mini_wm_SOURCES       = mini-wm.c

udevdir               = /lib/udev/rules.d
dist_udev_DATA        = 70-anaconda.rules

langdir               = $(libdir)/$(PACKAGE_NAME)
lang_DATA             = lang-names
dist_lang_DATA        = lang-table

pkgpyexecdir          = $(libdir)/$(PACKAGE_NAME)
pkgpythondir          = $(libdir)/$(PACKAGE_NAME)

pkgpyexec_LTLIBRARIES = xutils.la
xutils_la_CFLAGS      = $(PYTHON_INCLUDES) $(GDK_CFLAGS) -fno-strict-aliasing
xutils_la_LDFLAGS     = -module -avoid-version $(PYTHON_LDFLAGS) $(GDK_LDFLAGS)
xutils_la_LIBADD      = $(PYTHON_LIBS) $(GDK_LIBS)
xutils_la_SOURCES     = xutils.c

# anaconda Python code
anacondadir = $(libdir)/$(PACKAGE_NAME)
anaconda_PYTHON = *.py

PYCHECKERPATH = isys:textw:iw:installclasses:/usr/share/system-config-date
PYCHECKEROPTS = -F pycheckrc-for-anaconda
ARCHIVE_TAG   = $(PACKAGE_NAME)-$(PACKAGE_VERSION)-$(PACKAGE_RELEASE)

sed_verbose = $(sed_verbose_$(V))
sed_verbose_ = $(sed_verbose_$(AM_DEFAULT_VERBOSITY))
sed_verbose_0 = @echo "  SED    "$@;

$(PACKAGE_NAME).spec: $(PACKAGE_NAME).spec.in
	$(sed_verbose)sed -e 's/#VERSION#/$(PACKAGE_VERSION)/' < $< > $@

lang-names: lang-table
	PYTHONPATH="." $(PYTHON) scripts/getlangnames.py > lang-names

testiso: install
	@if [ "$(REPO)" = "" ]; then echo "ERROR: Need a repo to pull packages from!" ; exit 1 ; fi
	@pushd scripts ; sudo ./buildinstall --version $(PACKAGE_VERSION) --product $(PACKAGE_NAME) --release $(PACKAGE_NAME)-$(PACKAGE_VERSION) --output $(shell pwd)/outiso --updates $(DESTDIR) $(REPO) ; popd ; cp outiso/images/boot.iso ./boot.iso ; sudo rm -rf outiso
	@echo
	@echo "Test iso is located at ./boot.iso"

tag:
	@git tag -s -a -m "Tag as $(ARCHIVE_TAG)" $(ARCHIVE_TAG)
	@echo "Tagged as $(ARCHIVE_TAG)"

scratch:
	$(MAKE) ARCHIVE_TAG=HEAD dist

archive:
	$(MAKE) tag
	$(MAKE) dist
	git checkout -- po/$(PACKAGE_NAME).pot
	( cd po ; for f in *.po ; do git checkout -- $$f 2>/dev/null ; done )

release: archive

src: archive
	@rpmbuild -ts --nodeps $(PACKAGE_NAME)-$(PACKAGE_VERSION).tar.bz2 || exit 1
	@rm -f $(PACKAGE_NAME)-$(PACKAGE_VERSION).tar.bz2

pycheck:
	PYTHONPATH=$(PYCHECKERPATH) pychecker $(PYCHECKEROPTS) *.py textw/*.py iw/*.py installclasses/*.py storage/*.py | grep -v "__init__() not called"

pycheck-file:
	PYTHONPATH=.:$(PYCHECKERPATH) pychecker $(PYCHECKEROPTS) $(CHECK) | grep -v "__init__() not called"

api:
	doxygen docs/api.cfg

rpmlog:
	@git log --pretty="format:- %s (%ae)" \
		$(PACKAGE_NAME)-$(PACKAGE_VERSION)-$(PACKAGE_RELEASE).. | \
		sed -e 's/@.*)/)/' | sed -e 's/%/%%/g' | \
		grep -v -- "- l10n: " | \
		grep -v -- "- Merge commit "

bumpver:
	@LAST=$$(echo $(PACKAGE_VERSION) | grep "\." -o | wc -l) ; \
	FIELD=$$(($${LAST} + 1)) ; \
	NEWSUBVER=$$((`echo $(PACKAGE_VERSION) | cut -d . -f $${FIELD}` + 1)) ; \
	NEWVERSION="`echo $(PACKAGE_VERSION) | cut -d . -f 1-$${LAST}`.$$NEWSUBVER" ; \
	DATELINE="* `date "+%a %b %d %Y"` `git config user.name` <`git config user.email`> - $$NEWVERSION-1"  ; \
	cl=`grep -n %changelog anaconda.spec.in |cut -d : -f 1` ; \
	tail --lines=+$$(($$cl + 1)) anaconda.spec.in > speclog ; \
	make --quiet rpmlog 2>/dev/null | fold -s -w 77 | while read line ; do \
		if [ ! "$$(echo $$line | cut -c-2)" = "- " ]; then \
			echo "  $$line" ; \
		else \
			echo "$$line" ; \
		fi ; \
	done > newspeclog ; \
	(head -n $$cl anaconda.spec.in ; echo "$$DATELINE" ; cat newspeclog ; echo ""; cat speclog) > anaconda.spec.in.new ; \
	mv anaconda.spec.in.new anaconda.spec.in ; rm -f speclog ; rm -f newspeclog ; \
	sed -i "s/AC_INIT(\[$(PACKAGE_NAME)\], \[$(PACKAGE_VERSION)\], \[$(PACKAGE_BUGREPORT\])/AC_INIT(\[$(PACKAGE_NAME)\], \[$$NEWVERSION\], \[$(PACKAGE_BUGREPORT\])/" configure.ac
	$(MAKE) -C po $(PACKAGE_NAME).pot-update

install-buildrequires:
	yum install $$(grep BuildRequires: anaconda.spec.in | cut -d ' ' -f 2)

# Generate an updates.img based on the changed files since the release
# was tagged.  Updates are copied to ./updates-img and then the image is
# created.  By default, the updates subdirectory is removed after the
# image is made, but if you want to keep it around, run:
#     make updates.img KEEP=y
updates:
	@opts="-c" ; \
	keep="$$(echo $(KEEP) | cut -c1 | tr [a-z] [A-Z])" ; \
	if [ "$${keep}" = "Y" ]; then \
		opts="$${opts} -k" ; \
	fi ; \
	scripts/makeupdates $${opts}

# DEPRECATED TARGETS:
archive-no-tag: dist

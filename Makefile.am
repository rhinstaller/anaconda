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

SUBDIRS = data docs dracut po pyanaconda scripts tests widgets utils

EXTRA_DIST = config.rpath COPYING

MAINTAINERCLEANFILES = Makefile.in config.guess config.h.in config.sub \
                       depcomp install-sh ltmain.sh missing ABOUT-NLS \
                       INSTALL aclocal.m4 configure *.pyc py-compile \
		       m4/* config.rpath po/Makefile.in.in po/Rules-quot \
		       test-driver

CLEANFILES = *~

MOSTLYCLEANDIRS = m4

dist_noinst_DATA      = $(PACKAGE_NAME).spec

dist_sbin_SCRIPTS     = anaconda

ARCHIVE_TAG   = $(PACKAGE_NAME)-$(PACKAGE_VERSION)-$(PACKAGE_RELEASE)

TX_PULL_ARGS = -a --disable-overwrite
TX_PUSH_ARGS = -s

tag:
	@git tag -s -a -m "Tag as $(ARCHIVE_TAG)" $(ARCHIVE_TAG)
	@echo "Tagged as $(ARCHIVE_TAG)"

po-pull:
	rm -f $(srcdir)/po/en@boldquot.gmo $(srcdir)/po/en@boldquot.po
	rm -f $(srcdir)/po/en@quot.gmo $(srcdir)/po/en@quot.po
	rpm -q transifex-client &>/dev/null || ( echo "need to run: yum install transifex-client"; exit 1 )
	tx pull $(TX_PULL_ARGS)

scratch: po-pull
	$(MAKE) ARCHIVE_TAG=HEAD dist
	git checkout -- $(srcdir)/po/$(PACKAGE_NAME).pot

scratch-bumpver: po-pull
	@opts="-n $(PACKAGE_NAME) -v $(PACKAGE_VERSION) -r $(PACKAGE_RELEASE) -b $(PACKAGE_BUGREPORT)" ; \
	if [ ! -z "$(IGNORE)" ]; then \
		opts="$${opts} -i $(IGNORE)" ; \
	fi ; \
	if [ ! -z "$(MAP)" ]; then \
		opts="$${opts} -m $(MAP)" ; \
	fi ; \
	if [ ! -z "$(BZDEBUG)" ]; then \
		opts="$${opts} -d" ; \
	fi ; \
	( cd $(srcdir) && scripts/makebumpver $${opts} ) || exit 1 ; \
	$(MAKE) -C po $(PACKAGE_NAME).pot-update ; 

release:
	$(MAKE) dist && $(MAKE) tag && git checkout -- $(srcdir)/po/$(PACKAGE_NAME).pot

api:
	doxygen docs/api.cfg

bumpver: po-pull
	@opts="-n $(PACKAGE_NAME) -v $(PACKAGE_VERSION) -r $(PACKAGE_RELEASE) -b $(PACKAGE_BUGREPORT)" ; \
	if [ ! -z "$(IGNORE)" ]; then \
		opts="$${opts} -i $(IGNORE)" ; \
	fi ; \
	if [ ! -z "$(MAP)" ]; then \
		opts="$${opts} -m $(MAP)" ; \
	fi ; \
	if [ ! -z "$(BZDEBUG)" ]; then \
		opts="$${opts} -d" ; \
	fi ; \
	( cd $(srcdir) && scripts/makebumpver $${opts} ) || exit 1 ; \
	$(MAKE) -C po $(PACKAGE_NAME).pot-update && \
	tx push $(TX_PUSH_ARGS)

# Install all packages specified as BuildRequires in the Anaconda specfile
# -> installs packages needed to build Anaconda
install-buildrequires:
	srcdir="$(srcdir)" && \
	: $${srcdir:=.} && \
	yum install $$(grep BuildRequires: $${srcdir}/anaconda.spec.in | cut -d ' ' -f 2)

# Install all packages specified as Requires in the Anaconda specfile
# -> installs packages needed to run Anaconda and the Anaconda unit tests
install-requires:
	srcdir="$(srcdir)" && \
	: $${srcdir:=.} && \
	yum install $$(grep Requires: $${srcdir}/anaconda.spec.in | cut -d ' ' -f 2)

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
	( cd $(srcdir) && scripts/makeupdates $${opts} -b '$(abs_builddir)' )

# UNIT TESTING TARGETS
unittests-logpicker:
	PYTHONPATH=$(builddir)/pyanaconda/isys/.libs:tests/:$(srcdir):utils/ nosetests -v old_tests/logpicker_test

# GUI TESTING
runspoke:
	ANACONDA_DATA=$(srcdir)/data \
	ANACONDA_WIDGETS_OVERRIDES=$(srcdir)/widgets/python \
	ANACONDA_WIDGETS_DATA=$(srcdir)/widgets/data \
	ANACONDA_INSTALL_CLASSES=$(srcdir)/pyanaconda/installclasses \
	PYTHONPATH=$(srcdir):$(builddir)/pyanaconda/isys/.libs:$(srcdir)/widgets/python/:$(builddir)/widgets/src/.libs/ \
	LD_LIBRARY_PATH=$(builddir)/widgets/src/.libs \
	UIPATH=$(srcdir)/pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=$(builddir)/widgets/src/ \
	$(srcdir)/pyanaconda/ui/gui/tools/run-spoke.py ${SPOKE_MODULE} ${SPOKE_CLASS}

runhub:
	ANACONDA_DATA=$(srcdir)/data \
	ANACONDA_WIDGETS_OVERRIDES=$(srcdir)/widgets/python \
	ANACONDA_WIDGETS_DATA=$(srcdir)/widgets/data \
	ANACONDA_INSTALL_CLASSES=$(srcdir)/pyanaconda/installclasses \
	PYTHONPATH=$(srcdir):$(builddir)/pyanaconda/isys/.libs:$(srcdir)/widgets/python/:$(builddir)/widgets/src/.libs/ \
	LD_LIBRARY_PATH=$(builddir)/widgets/src/.libs \
	UIPATH=$(srcdir)/pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=$(builddir)/widgets/src/ \
	$(srcdir)/pyanaconda/ui/gui/tools/run-hub.py ${HUB_MODULE} ${HUB_CLASS}

runtextspoke:
	ANACONDA_DATA=$(srcdir)/data \
	ANACONDA_INSTALL_CLASSES=$(srcdir)/pyanaconda/installclasses \
	PYTHONPATH=$(srcdir):$(builddir)/pyanaconda/isys/.libs:$(srcdir)/widgets/python/:$(builddir)/widgets/src/.libs/ \
	LD_LIBRARY_PATH=$(builddir)/widgets/src/.libs \
	$(srcdir)/pyanaconda/ui/tui/tools/run-text-spoke.py ${SPOKE_MODULE} ${SPOKE_CLASS}

runtexthub:
	ANACONDA_DATA=$(srcdir)/data \
	ANACONDA_INSTALL_CLASSES=$(srcdir)/pyanaconda/installclasses \
	PYTHONPATH=$(srcdir):$(builddir)/pyanaconda/isys/.libs:$(srcdir)/widgets/python/:$(builddir)/widgets/src/.libs/ \
	LD_LIBRARY_PATH=$(builddir)/widgets/src/.libs \
	$(srcdir)/pyanaconda/ui/tui/tools/run-text-hub.py ${HUB_MODULE} ${HUB_CLASS}


runglade:
	ANACONDA_DATA=$(srcdir)/data \
	ANACONDA_WIDGETS_OVERRIDES=$(srcdir)/widgets/python \
	ANACONDA_WIDGETS_DATA=$(srcdir)/widgets/data \
	ANACONDA_INSTALL_CLASSES=$(srcdir)/pyanaconda/installclasses \
	PYTHONPATH=$(srcdir):$(builddir)/pyanaconda/isys/.libs:$(srcdir)/widgets/python/:$(builddir)/widgets/src/.libs/ \
	LD_LIBRARY_PATH=$(builddir)/widgets/src/.libs \
	UIPATH=$(srcdir)/pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=$(builddir)/widgets/src/ \
	GLADE_CATALOG_SEARCH_PATH=$(srcdir)/widgets/glade \
	GLADE_MODULE_SEARCH_PATH=$(builddir)/widgets/src/.libs \
	glade ${GLADE_FILE}

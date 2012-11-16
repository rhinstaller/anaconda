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

SUBDIRS = pyanaconda po data \
	  tests utils scripts docs dracut widgets

EXTRA_DIST = config.rpath COPYING \
             anaconda.spec.in

MAINTAINERCLEANFILES = Makefile.in config.guess config.h.in config.sub \
                       depcomp install-sh ltmain.sh missing ABOUT-NLS \
                       INSTALL aclocal.m4 configure *.pyc py-compile

CLEANFILES = *~ anaconda.spec

MOSTLYCLEANDIRS = m4

dist_noinst_DATA      = $(PACKAGE_NAME).spec

dist_sbin_SCRIPTS     = anaconda

ARCHIVE_TAG   = $(PACKAGE_NAME)-$(PACKAGE_VERSION)-$(PACKAGE_RELEASE)

sed_verbose = $(sed_verbose_$(V))
sed_verbose_ = $(sed_verbose_$(AM_DEFAULT_VERBOSITY))
sed_verbose_0 = @echo "  SED    "$@;

TX_PULL_ARGS = -a --disable-overwrite
TX_PUSH_ARGS = -s

$(PACKAGE_NAME).spec: $(PACKAGE_NAME).spec.in
	$(sed_verbose)sed -e 's/#VERSION#/$(PACKAGE_VERSION)/' < $< > $@

tag:
	@git tag -s -a -m "Tag as $(ARCHIVE_TAG)" $(ARCHIVE_TAG)
	@echo "Tagged as $(ARCHIVE_TAG)"

po-pull:
	rm -f po/en@boldquot.gmo po/en@boldquot.po
	rm -f po/en@quot.gmo po/en@quot.po
	rpm -q transifex-client &>/dev/null || ( echo "need to run: yum install transifex-client"; exit 1 )
	tx pull $(TX_PULL_ARGS)

scratch: po-pull
	$(MAKE) ARCHIVE_TAG=HEAD dist
	git checkout -- po/$(PACKAGE_NAME).pot

release:
	$(MAKE) dist && $(MAKE) tag && git checkout -- po/$(PACKAGE_NAME).pot

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
	scripts/makebumpver $${opts} || exit 1 ; \
	$(MAKE) -C po $(PACKAGE_NAME).pot-update ; \
	tx push $(TX_PUSH_ARGS)

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

# UNIT TESTING TARGETS
unittest:
	PYTHONPATH=tests/:. nosetests --exclude=logpicker -a \!acceptance,\!slow  tests/

unittests-logpicker:
	PYTHONPATH=tests/:.:utils/ nosetests tests/logpicker_test

# GUI TESTING
runspoke:
	ANACONDA_DATA=${PWD}/data \
	ANACONDA_WIDGETS_OVERRIDES=${PWD}/widgets/python \
	ANACONDA_WIDGETS_DATA=${PWD}/widgets/data \
	ANACONDA_INSTALL_CLASSES=${PWD}/pyanaconda/installclasses \
	PYTHONPATH=.:pyanaconda/isys/.libs:widgets/python/:widgets/src/.libs/ \
	LD_LIBRARY_PATH=widgets/src/.libs \
	UIPATH=pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=widgets/src/ \
	pyanaconda/ui/gui/tools/run-spoke.py ${SPOKE_MODULE} ${SPOKE_CLASS}

runhub:
	ANACONDA_DATA=${PWD}/data \
	ANACONDA_WIDGETS_OVERRIDES=${PWD}/widgets/python \
	ANACONDA_WIDGETS_DATA=${PWD}/widgets/data \
	ANACONDA_INSTALL_CLASSES=${PWD}/pyanaconda/installclasses \
	PYTHONPATH=.:pyanaconda/isys/.libs:widgets/python/:widgets/src/.libs/ \
	LD_LIBRARY_PATH=widgets/src/.libs \
	UIPATH=pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=widgets/src/ \
	pyanaconda/ui/gui/tools/run-hub.py ${HUB_MODULE} ${HUB_CLASS}

runtextspoke:
	ANACONDA_DATA=${PWD}/data \
	ANACONDA_INSTALL_CLASSES=${PWD}/pyanaconda/installclasses \
	PYTHONPATH=.:pyanaconda/isys/.libs:widgets/python/:widgets/src/.libs/ \
	LD_LIBRARY_PATH=widgets/src/.libs \
	pyanaconda/ui/tui/tools/run-text-spoke.py ${SPOKE_MODULE} ${SPOKE_CLASS}

runtexthub:
	ANACONDA_DATA=${PWD}/data \
	ANACONDA_INSTALL_CLASSES=${PWD}/pyanaconda/installclasses \
	PYTHONPATH=.:pyanaconda/isys/.libs:widgets/python/:widgets/src/.libs/ \
	LD_LIBRARY_PATH=widgets/src/.libs \
	pyanaconda/ui/tui/tools/run-text-hub.py ${HUB_MODULE} ${HUB_CLASS}


runglade:
	ANACONDA_DATA=${PWD}/data \
	ANACONDA_WIDGETS_OVERRIDES=${PWD}/widgets/python \
	ANACONDA_WIDGETS_DATA=${PWD}/widgets/data \
	ANACONDA_INSTALL_CLASSES=${PWD}/pyanaconda/installclasses \
	PYTHONPATH=.:pyanaconda/isys/.libs:widgets/python/:widgets/src/.libs/ \
	LD_LIBRARY_PATH=widgets/src/.libs \
	UIPATH=pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=widgets/src/ \
	GLADE_CATALOG_SEARCH_PATH=${PWD}/widgets/glade \
	GLADE_MODULE_SEARCH_PATH=${PWD}/widgets/src/.libs \
	glade ${GLADE_FILE}

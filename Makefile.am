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

SUBDIRS = pyanaconda loader gptsync data \
	  tests utils scripts docs po

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

$(PACKAGE_NAME).spec: $(PACKAGE_NAME).spec.in
	$(sed_verbose)sed -e 's/#VERSION#/$(PACKAGE_VERSION)/' < $< > $@

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

api:
	doxygen docs/api.cfg

bumpver:
	@opts="-n $(PACKAGE_NAME) -v $(PACKAGE_VERSION) -r $(PACKAGE_RELEASE) -b $(PACKAGE_BUGREPORT)" ; \
	if [ ! -z "$(IGNORE)" ]; then \
		opts="$${opts} -i $(IGNORE)" ; \
	fi ; \
	if [ ! -z "$(MAP)" ]; then \
		opts="$${opts} -m $(MAP)" ; \
	fi ; \
	scripts/makebumpver $${opts} || exit 1 ; \
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

# UNIT TESTING TARGETS
unittest:
	PYTHONPATH=tests/:. nosetests -w tests/ -a \!acceptance,\!slow

fulltest:
	PYTHONPATH=tests/:. nosetests -w tests/

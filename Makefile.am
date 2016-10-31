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

ACLOCAL_AMFLAGS = -I m4

SUBDIRS = data docs dracut po pyanaconda scripts tests widgets utils

EXTRA_DIST = COPYING .coveragerc

# Include the xgettext wrapper so pot-update can be run from the source distribution
# This is needed for make distcheck.
EXTRA_DIST += $(srcdir)/translation-canary/xgettext_werror.sh

MAINTAINERCLEANFILES = Makefile.in config.guess config.h.in config.sub \
                       depcomp install-sh ltmain.sh missing ABOUT-NLS \
                       INSTALL aclocal.m4 configure *.pyc py-compile \
		       m4/* po/Makefile.in.in po/Rules-quot \
		       test-driver

CLEANFILES = *~

dist_noinst_DATA      = $(PACKAGE_NAME).spec

dist_sbin_SCRIPTS     = anaconda.py

install-exec-hook:
	cd $(DESTDIR)$(sbindir) && mv anaconda.py anaconda

uninstall-hook:
	-cd $(DESTDIR)$(sbindir) && rm -f anaconda

ARCHIVE_TAG   = $(PACKAGE_NAME)-$(PACKAGE_VERSION)-$(PACKAGE_RELEASE)

ZANATA_PULL_ARGS = --transdir $(srcdir)/po/
ZANATA_PUSH_ARGS = --srcfile $(srcdir)/po/anaconda.pot --push-type source --force

RC_RELEASE ?= $(shell date -u +0.1.%Y%m%d%H%M%S)
MOCKCHROOT ?= fedora-25-$(shell uname -m)

COVERAGE ?= coverage3
USER_SITE_BASE ?= $(abs_top_builddir)/python-site
USER_SITE_PACKAGES ?= $(shell PYTHONUSERBASE=$(USER_SITE_BASE) $(PYTHON) -m site --user-site)

# If translations are present, run tests on the .po files before tarring them
# up. Use a weird looking loop because shell doesn't have a good way to test
# for a wildcard
dist-hook:
	for p in $(distdir)/po/*.po ; do \
	    if [ -e "$$p" ]; then \
		PYTHONPATH=$(srcdir)/translation-canary python3 -m translation_canary.translated \
		    --release $(distdir)/po ; \
	    fi ; \
	    break ; \
	done

tag:
	@git tag -s -a -m "Tag as $(ARCHIVE_TAG)" $(ARCHIVE_TAG)
	@echo "Tagged as $(ARCHIVE_TAG)"

po-pull:
	rpm -q zanata-python-client &>/dev/null || ( echo "need to run: dnf install zanata-python-client"; exit 1 )
	( cd $(srcdir) && zanata pull $(ZANATA_PULL_ARGS) )

# Try to fetch translations, but if that fails just keep going
po-fallback:
	-$(MAKE) po-pull

scratch:
	$(MAKE) ARCHIVE_TAG=HEAD dist

scratch-bumpver:
	@opts="-S -n $(PACKAGE_NAME) -v $(PACKAGE_VERSION) -r $(PACKAGE_RELEASE) -b $(PACKAGE_BUGREPORT) --newrelease $(RC_RELEASE)" ; \
	if [ ! -z "$(IGNORE)" ]; then \
		opts="$${opts} -i $(IGNORE)" ; \
	fi ; \
	if [ ! -z "$(MAP)" ]; then \
		opts="$${opts} -m $(MAP)" ; \
	fi ; \
	if [ ! -z "$(BZDEBUG)" ]; then \
		opts="$${opts} -d" ; \
	fi ; \
	( cd $(srcdir) && scripts/makebumpver --skip-zanata $${opts} ) || exit 1 ; \
	$(MAKE) -C po $(PACKAGE_NAME).pot-update

release:
	$(MAKE) dist && $(MAKE) tag

rc-release: scratch-bumpver scratch
	mock -r $(MOCKCHROOT) --scrub all || exit 1
	mock -r $(MOCKCHROOT) --buildsrpm  --spec ./$(PACKAGE_NAME).spec --sources . --resultdir $(PWD) || exit 1
	mock -r $(MOCKCHROOT) --rebuild *src.rpm --resultdir $(PWD) || exit 1

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
	if [ ! -z "$(SKIP_ACKS)" ]; then \
		opts="$${opts} -s" ; \
	fi ; \
	( cd $(srcdir) && scripts/makebumpver $${opts} ) || exit 1 ; \
	$(MAKE) -C po $(PACKAGE_NAME).pot-update && \
	rm $(srcdir)/po/{main,extra}.pot
	zanata push $(ZANATA_PUSH_ARGS)

# Install all packages specified as BuildRequires in the Anaconda specfile
# -> installs packages needed to build Anaconda
# don't try to install s390utils-devel on non-s390 arches
install-buildrequires:
	srcdir="$(srcdir)" && \
	: $${srcdir:=.} && \
	pkglist="$$(grep ^BuildRequires: $${srcdir}/anaconda.spec.in | cut -d ' ' -f 2)" && \
	if ! [[ $$(uname -m) =~ s390x? ]]; then \
		pkglist=$$(echo "$$pkglist" | grep -v s390utils) ; \
	fi ; \
	extra_pkgs="gettext-devel libtool glibc-langpack-en python3-pocketlint" ; \
	dnf install $$pkglist $$extra_pkgs

# Install all packages specified as Requires in the Anaconda specfile
# -> installs packages needed to run Anaconda and the Anaconda unit tests
# Filter out the %{name} entries required by -devel
install-requires:
	srcdir="$(srcdir)" && \
	: $${srcdir:=.} && \
	dnf install $$(grep ^Requires: $${srcdir}/anaconda.spec.in | grep -v %{name} | cut -d ' ' -f 2 | grep -v ^anaconda)

# Install all packages required for running the tests
install-test-requires: install-buildrequires install-requires
		dnf install bzip2 cppcheck \
		    lorax mock parallel rpm-ostree virt-install pykickstart spin-kickstarts  \
		    python3-rpmfluff python3-mock python3-pocketlint python3-nose-testconfig \
		    python3-sphinx_rtd_theme libvirt-python3 python3-lxml python3-dogtail    \
		    qemu-img

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

# GUI TESTING
runglade:
	ANACONDA_DATA=$(srcdir)/data \
	ANACONDA_WIDGETS_OVERRIDES=$(srcdir)/widgets/python \
	ANACONDA_INSTALL_CLASSES=$(srcdir)/pyanaconda/installclasses \
	PYTHONPATH=$(srcdir):$(builddir)/pyanaconda/isys/.libs:$(srcdir)/widgets/python/:$(builddir)/widgets/src/.libs/ \
	LD_LIBRARY_PATH=$(builddir)/widgets/src/.libs \
	UIPATH=$(srcdir)/pyanaconda/ui/gui/ \
	GI_TYPELIB_PATH=$(builddir)/widgets/src/ \
	GLADE_CATALOG_SEARCH_PATH=$(srcdir)/widgets/glade \
	GLADE_MODULE_SEARCH_PATH=$(builddir)/widgets/src/.libs \
	glade ${GLADE_FILE}

ci: rc-release
	@rm -f tests/test-suite.log.*
	@mkdir -p $(USER_SITE_PACKAGES)
	@cp $(abs_builddir)/tests/usercustomize.py $(USER_SITE_PACKAGES)
	$(MAKE)
	$(MAKE) TMPDIR=/var/tmp COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		TEST_SUITE_LOG=test-suite.log.$$$$ PYTHONUSERBASE=$(USER_SITE_BASE) check
	@tail -n 1 tests/gettext_tests/*.log > tests/gettext_tests/gettext_tests.log
	@sudo $(MAKE) TMPDIR=/var/tmp COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		TEST_SUITE_LOG=test-suite.log.$$$$ TESTS=nosetests_root.sh \
		PYTHONUSERBASE=$(USER_SITE_BASE) check
	@mkdir -p repo
	@mv *rpm repo
	@createrepo_c -p repo
	@sudo $(MAKE) TMPDIR=/var/tmp COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		TEST_SUITE_LOG=test-suite.log.$$$$ TESTS=install/run_install_test.sh \
		TEST_ANACONDA_REPO=file://$(abs_builddir)/repo/ PYTHONUSERBASE=$(USER_SITE_BASE) check
	@cat tests/test-suite.log.* > tests/test-suite.log
	@rm -f tests/test-suite.log.*
	@rm -rf $(USER_SITE_BASE)
	$(MAKE) coverage-report

test-gui:
	@rm -f tests/test-suite.log
	@rm -rf tests/autogui-results-*/
	@mkdir -p $(USER_SITE_PACKAGES)
	@cp $(abs_builddir)/tests/usercustomize.py $(USER_SITE_PACKAGES)
	$(MAKE) -C pyanaconda/isys
	sudo COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		PYTHONPATH=$(builddir)/pyanaconda/isys/.libs \
		PYTHONUSERBASE=$(USER_SITE_BASE) \
		$(abs_builddir)/tests/run_gui_tests.sh >tests/test-suite.log 2>&1
	@rm -rf $(USER_SITE_BASE)
	@cat tests/test-suite.log
	@mv .coverage.* tests/
	$(MAKE) coverage-report

coverage-report:
	$(COVERAGE) combine tests/.coverage.*
	$(COVERAGE) report --omit "tests/*" > tests/coverage-report.log
	@cat tests/coverage-report.log

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

MAINTAINERCLEANFILES =	Makefile.in config.guess config.h.in config.sub \
						depcomp install-sh ltmain.sh missing ABOUT-NLS \
						INSTALL aclocal.m4 configure *.pyc \
						py-compile m4/* po/Makefile.in.in po/Rules-quot \
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

DIST_NAME ?= $(shell echo "$(GIT_BRANCH)" | sed \
				-e 's/^f//' \
				-e 's/master/rawhide/')
ARCH_NAME ?= $(shell uname -m)

RC_RELEASE ?= $(shell date -u +0.1.%Y%m%d%H%M%S)

MOCKCHROOT ?= fedora-$(DIST_NAME)-$(ARCH_NAME)
MOCK_EXTRA_ARGS ?=

COVERAGE ?= coverage3
USER_SITE_BASE ?= $(abs_top_builddir)/python-site
USER_SITE_PACKAGES ?= $(shell PYTHONUSERBASE=$(USER_SITE_BASE) $(PYTHON) -m site --user-site)

RESULT_DIR ?= $(abs_top_builddir)/result
BUILD_RESULT_DIR = $(RESULT_DIR)/build
TEST_RESULT_DIR = $(RESULT_DIR)/tests

SRPM_BUILD_DIR = $(BUILD_RESULT_DIR)/00-srpm-build
RPM_BUILD_DIR = $(BUILD_RESULT_DIR)/01-rpm-build
TEST_INST_BUILD_DIR = $(BUILD_RESULT_DIR)/02-test-install

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

po-push:
	$(MAKE) -C po $(PACKAGE_NAME).pot-update
	rm $(srcdir)/po/{main,extra}.pot
	zanata push $(ZANATA_PUSH_ARGS)

po-all:
	$(MAKE) po-push
	$(MAKE) po-pull

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
	$(MAKE) po-all
	$(MAKE) dist

release-and-tag:
	$(MAKE) dist
	$(MAKE) tag

rc-release: scratch-bumpver scratch
	-rm -rf $(BUILD_RESULT_DIR)
	mock -r $(MOCKCHROOT) $(MOCK_EXTRA_ARGS) --clean || exit 1
	mock -r $(MOCKCHROOT) $(MOCK_EXTRA_ARGS) --buildsrpm  --spec ./$(PACKAGE_NAME).spec --sources . --resultdir $(SRPM_BUILD_DIR) || exit 1
	mock -r $(MOCKCHROOT) $(MOCK_EXTRA_ARGS) --rebuild $(SRPM_BUILD_DIR)/*src.rpm --resultdir $(RPM_BUILD_DIR) || exit 1

test-install: rc-release
	mock -r $(MOCKCHROOT) $(MOCK_EXTRA_ARGS) --clean || exit 1
	mock -r $(MOCKCHROOT) $(MOCK_EXTRA_ARGS) --install $(RPM_BUILD_DIR)/anaconda-*$(ARCH_NAME).rpm --resultdir $(TEST_INST_BUILD_DIR)

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
		dnf install \
			xfsprogs git bzip2 cppcheck rpm-ostree pykickstart spin-kickstarts  \
		    python3-rpmfluff python3-mock python3-pocketlint python3-nose-testconfig \
		    python3-sphinx_rtd_theme python3-lxml python3-dogtail sudo

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

ci:
# clean result dir
	-rm -rf $(TEST_RESULT_DIR)
	mkdir -p $(TEST_RESULT_DIR)

# run tests
	$(MAKE) run-tests || echo $$? > $(srcdir)/tests/error_occured

# grab logs
	cd $(top_builddir)/tests/ && cp -r --parents ./**/*.log ./*.log* $(TEST_RESULT_DIR) || exit 1
	-mv $(TEST_RESULT_DIR)/test-suite.log.* $(TEST_RESULT_DIR)/test-suite.log
	@if [ -f $(srcdir)/tests/error_occured ]; then \
		echo "TEST FAILED"; \
		status=$$(cat $(srcdir)/tests/error_occured); \
		rm $(srcdir)/tests/error_occured; \
		exit $$status; \
	fi

run-tests:
	@mkdir -p $(USER_SITE_PACKAGES)
	@cp $(abs_builddir)/tests/usercustomize.py $(USER_SITE_PACKAGES)
	$(MAKE)
	$(MAKE) TMPDIR=/var/tmp COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		TEST_SUITE_LOG=test-suite.log.$$$$ PYTHONUSERBASE=$(USER_SITE_BASE) check
	@tail -n 1 tests/gettext_tests/*.log > tests/gettext_tests/gettext_tests.log
	@sudo $(MAKE) TMPDIR=/var/tmp COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		TEST_SUITE_LOG=test-suite.log.$$$$ TESTS=nosetests_root.sh \
		PYTHONUSERBASE=$(USER_SITE_BASE) check
	@sudo $(MAKE) TMPDIR=/var/tmp COVERAGE_PROCESS_START=$(abs_builddir)/.coveragerc \
		TEST_SUITE_LOG=test-suite.log.$$$$ PYTHONUSERBASE=$(USER_SITE_BASE) check
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

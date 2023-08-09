# Copyright (C) 2021  Red Hat, Inc.
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


SUBDIRS =
MAINTAINERCLEANFILES = Makefile.in

# stamp file to check if/when npm install ran
# one example file in dist/ to check if that already ran
WEBPACK_TEST=dist/manifest.json
WEBPACK_TEST_PRODUCTION=dist/index.css.gz
PACKAGE_NAME=anaconda-webui
# one example file in pkg/lib to check if it was already checked out
COCKPIT_REPO_STAMP=pkg/lib/cockpit-po-plugin.js
# stamp file to check if/when npm install ran
NODE_MODULES_TEST=package-lock.json
TEST_OS=fedora-rawhide-boot
PAYLOAD=fedora-rawhide-anaconda-payload
GITHUB_BASE=rhinstaller/anaconda
UPDATES_IMG=../../updates.img

export GITHUB_BASE
export TEST_OS

dist_libexec_SCRIPTS = webui-desktop
# makes sure it gets built as part of `make` and `make dist`
dist_noinst_DATA = \
	$(WEBPACK_TEST) \
	$(COCKPIT_REPO_STAMP) \
	org.cockpit-project.anaconda-webui.metainfo.xml \
	package-lock.json \
	package.json \
	build.js

$(WEBPACK_TEST): $(COCKPIT_REPO_STAMP) $(shell find src/ -type f) $(NODE_MODULES_TEST) package.json build.js
	NODE_ENV=production ./build.js

watch:
	rm -f dist/*
	NODE_ENV=$(NODE_ENV) ESBUILD_WATCH=true ./build.js

rsync:
	RSYNC=$${RSYNC:-test-updates} make watch

install-data-hook: $(WEBPACK_TEST)
	mkdir -p $(DESTDIR)/usr/share/cockpit/$(PACKAGE_NAME)
	cp -r dist/* $(DESTDIR)/usr/share/cockpit/$(PACKAGE_NAME)
	mkdir -p $(DESTDIR)/usr/share/anaconda
	cp -r firefox-theme $(DESTDIR)/usr/share/anaconda/
	mkdir -p $(DESTDIR)/usr/share/metainfo/
	cp org.cockpit-project.$(PACKAGE_NAME).metainfo.xml $(DESTDIR)/usr/share/metainfo/
	cp webui-desktop $(DESTDIR)/usr/libexec/

EXTRA_DIST = dist src firefox-theme

# checkout common files from Cockpit repository required to build this project;
# this has no API stability guarantee, so check out a stable tag when you start
# a new project, use the latest release, and update it from time to time
COCKPIT_REPO_FILES = \
	pkg/lib \
	test/common \
	tools/git-utils.sh \
	tools/make-bots \
	$(NULL)

COCKPIT_REPO_URL = https://github.com/cockpit-project/cockpit.git
COCKPIT_REPO_COMMIT = 84c7ee507b57485b5edd97ed3321982a59032f20 # 289 + run-tests machine_class fix

$(COCKPIT_REPO_FILES): $(COCKPIT_REPO_STAMP)
COCKPIT_REPO_TREE = '$(strip $(COCKPIT_REPO_COMMIT))^{tree}'
$(COCKPIT_REPO_STAMP): Makefile.am
	@git rev-list --quiet --objects $(COCKPIT_REPO_TREE) -- 2>/dev/null || \
	     git fetch --no-tags --no-write-fetch-head --depth=1 $(COCKPIT_REPO_URL) $(COCKPIT_REPO_COMMIT)
	git -C ../../ archive $(COCKPIT_REPO_TREE) -- $(COCKPIT_REPO_FILES) | tar x

# checkout Cockpit's bots for standard test VM images and API to launch them
# must be from main, as only that has current and existing images; but testvm.py API is stable
# support CI testing against a bots change
# Workaround cockpit's expectation for test/images directory. This is not really needed in our case
# as we consume ready ISOs
# https://github.com/cockpit-project/cockpit/blob/main/test/common/testlib.py#L1118
bots: tools/make-bots
	GITHUB_BASE="cockpit-project/cockpit" tools/make-bots
	cd test && ln -sf ../bots/images images

live-vm: bots $(UPDATES_IMG)
	./test/testvm.py $(TEST_LIVE_OS)

prepare-test-deps: bots test/common payload

.PHONY: payload
payload: bots
	bots/image-download $(PAYLOAD)

$(UPDATES_IMG): bots
	test/prepare-updates-img

create-updates.img: bots
	-rm $(UPDATES_IMG)
	make $(UPDATES_IMG)

# test runs in kernel_t context and triggers massive amounts of SELinux
# denials; SELinux gets disabled, but would still trigger unexpected messages
integration-test: prepare-test-deps test/reference $(UPDATES_IMG)
	TEST_AUDIT_NO_SELINUX=1 test/common/run-tests

test/reference: test/common
	test/common/pixel-tests pull

update-reference-images: test/common test/reference
	test/common/pixel-tests push

$(NODE_MODULES_TEST): package.json
	rm -f package-lock.json #  if it exists already, npm install won't update it; force that so that we always get up-to-date packages
	env -u NODE_ENV npm install #  unset NODE_ENV, skips devDependencies otherwise
	env -u NODE_ENV npm prune

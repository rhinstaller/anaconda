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

# one example file in src/lib to check if it was already checked out
LIB_TEST=src/lib/cockpit-po-plugin.js
# stamp file to check if/when npm install ran
# one example file in dist/ from webpack to check if that already ran
WEBPACK_TEST=dist/manifest.json
WEBPACK_TEST_PRODUCTION=dist/index.css.gz
PACKAGE_NAME=anaconda-webui
# stamp file to check if/when npm install ran
NODE_MODULES_TEST=package-lock.json
TEST_OS=fedora-rawhide-boot
UPDATES_IMG=../../updates.img

export TEST_OS

# makes sure it gets built as part of `make` and `make dist`
dist_noinst_DATA = \
	$(WEBPACK_TEST) \
	org.cockpit-project.anaconda-webui.metainfo.xml \
	package-lock.json \
	package.json \
	webpack.config.js

$(WEBPACK_TEST): $(LIB_TEST) $(shell find src/ -type f) $(NODE_MODULES_TEST) package.json webpack.config.js
	NODE_ENV=production $(CURDIR)/node_modules/.bin/webpack

watch:
	rm -f dist/*
	NODE_ENV=$(NODE_ENV) node_modules/.bin/webpack --watch

rsync:
	RSYNC=test-updates make watch

install-data-hook: $(WEBPACK_TEST)
	mkdir -p $(DESTDIR)/usr/share/cockpit/$(PACKAGE_NAME)
	cp -r dist/* $(DESTDIR)/usr/share/cockpit/$(PACKAGE_NAME)
	mkdir -p $(DESTDIR)/usr/share/metainfo/
	cp org.cockpit-project.$(PACKAGE_NAME).metainfo.xml $(DESTDIR)/usr/share/metainfo/

EXTRA_DIST = dist src

# checkout Cockpit's PF/React/build library; again this has no API stability guarantee, so check out a stable tag
$(LIB_TEST):
	git clone -b 260 --depth=1 https://github.com/cockpit-project/cockpit.git tmp/cockpit
	mv tmp/cockpit/pkg/lib src/
	rm -rf tmp/cockpit

# checkout Cockpit's bots for standard test VM images and API to launch them
# must be from main, as only that has current and existing images; but testvm.py API is stable
# support CI testing against a bots change
bots:
	git clone --quiet --reference-if-able $${XDG_CACHE_HOME:-$$HOME/.cache}/cockpit-project/bots https://github.com/cockpit-project/bots.git
	if [ -n "$$COCKPIT_BOTS_REF" ]; then git -C bots fetch --quiet --depth=1 origin "$$COCKPIT_BOTS_REF"; git -C bots checkout --quiet FETCH_HEAD; fi
	@echo "checked out bots/ ref $$(git -C bots rev-parse HEAD)"

$(UPDATES_IMG):
	test/prepare-updates-img

integration-test: bots test/common $(UPDATES_IMG)
	test/run-tests

# checkout Cockpit's test API; this has no API stability guarantee, so check out a stable tag
# when you start a new project, use the latest release, and update it from time to time
test/common:
	git clone -b 263 --depth=1 https://github.com/cockpit-project/cockpit.git tmp/cockpit
	mv tmp/cockpit/test/common test/common
	rm -rf tmp/cockpit

$(NODE_MODULES_TEST): package.json
	rm -f package-lock.json #  if it exists already, npm install won't update it; force that so that we always get up-to-date packages
	env -u NODE_ENV npm install #  unset NODE_ENV, skips devDependencies otherwise
	env -u NODE_ENV npm prune

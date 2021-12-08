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

# one example file in src/lib to check if it was already checked out
LIB_TEST=src/lib/cockpit-po-plugin.js
# stamp file to check if/when npm install ran
# one example file in dist/ from webpack to check if that already ran
WEBPACK_TEST=dist/manifest.json
WEBPACK_TEST_PRODUCTION=dist/index.css.gz
PACKAGE_NAME=anaconda-webui

# makes sure it gets built as part of `make` and `make dist`
dist_noinst_DATA = \
	$(WEBPACK_TEST) \
	org.cockpit-project.anaconda-webui.metainfo.xml \
	package-lock.json \
	package.json \
	webpack.config.js

$(WEBPACK_TEST): $(LIB_TEST) $(shell find src/ -type f) package-lock.json webpack.config.js
	NODE_ENV=production $(CURDIR)/node_modules/.bin/webpack

install-data-hook: $(WEBPACK_TEST)
	mkdir -p $(DESTDIR)/usr/share/cockpit/$(PACKAGE_NAME)
	cp -r dist/* $(DESTDIR)/usr/share/cockpit/$(PACKAGE_NAME)
	mkdir -p $(DESTDIR)/usr/share/metainfo/
	cp org.cockpit-project.$(PACKAGE_NAME).metainfo.xml $(DESTDIR)/usr/share/metainfo/

EXTRA_DIST = dist src

# checkout Cockpit's PF/React/build library; again this has no API stability guarantee, so check out a stable tag
$(LIB_TEST):
	git clone -b 258 --depth=1 https://github.com/cockpit-project/cockpit.git tmp/cockpit
	mv tmp/cockpit/pkg/lib src/
	rm -rf tmp/cockpit

package-lock.json: package.json
	rm -f package-lock.json
	env -u NODE_ENV npm install
	env -u NODE_ENV npm prune

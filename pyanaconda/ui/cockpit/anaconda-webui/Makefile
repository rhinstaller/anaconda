# one example file in src/lib to check if it was already checked out
LIB_TEST=src/lib/cockpit-po-plugin.js

all: $(LIB_TEST)
	NODE_ENV=$(NODE_ENV) npm run build

clean:
	rm -rf dist/
	rm -rf _install

install: all
	mkdir -p /usr/share/cockpit/anaconda-webui
	cp -r dist/* /usr/share/cockpit/anaconda-webui

# when building a distribution tarball, call webpack with a 'production' environment
dist-gzip: NODE_ENV=production
dist-gzip: clean all
	mkdir -p _install/usr/share/cockpit
	cp -r dist/ _install/usr/share/cockpit/anaconda-webui
	mkdir -p _install/usr/share/metainfo/
	cp *.metainfo.xml _install/usr/share/metainfo/
	(cd _install; find -type f) | tar -C _install/ --mtime "$(stat -c '%Y' package.json)" --owner root --group root -cf anaconda-webui.tar -T -
	gzip -n anaconda-webui.tar
	rm -rf _install

# checkout Cockpit's PF/React/build library; again this has no API stability guarantee, so check out a stable tag
$(LIB_TEST):
	git clone -b 258 --depth=1 https://github.com/cockpit-project/cockpit.git tmp/cockpit
	mv tmp/cockpit/pkg/lib src/
	rm -rf tmp/cockpit

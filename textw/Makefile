all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/usr/lib/python1.5/site-packages/textw
	cp -a *.py $(DESTDIR)/usr/lib/python1.5/site-packages/textw
	../py-compile --basedir $(DESTDIR)/usr/lib/python1.5/site-packages/textw $(DESTDIR)/usr/lib/python1.5/site-packages/textw/*.py

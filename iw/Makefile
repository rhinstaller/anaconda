all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/usr/lib/python1.5/site-packages/iw
	cp -a *.py $(DESTDIR)/usr/lib/python1.5/site-packages/iw
	../py-compile --basedir $(DESTDIR)/usr/lib/python1.5/site-packages/iw $(DESTDIR)/usr/lib/python1.5/site-packages/iw/*.py

# Copyright (C) 1998-2002  Red Hat, Inc.
include Makefile.inc

SUBDIRSHD = isys loader2 po stubs \
	    textw utils scripts bootdisk installclasses \
	    fonts iw pixmaps isomd5sum command-stubs
SUBDIRS = $(SUBDIRSHD)

# DESTDIR        - destination for install image for install purposes
DESTDIR = ../../../RedHat/instimage

CATALOGS = po/anaconda.pot

PYFILES = $(wildcard *.py)

all:  subdirs mini-wm _xkb.so xmouse.so xutils.so $(CATALOGS) lang-table lang-names product.py locale-list

product.py: product.py.in Makefile.inc
	sed -e 's/@@PRODUCTNAME@@/$(PRODUCTNAME)/g' < product.py.in > product.py

lang-names: lang-table
	PYTHONPATH="." $(PYTHON) scripts/getlangnames.py > lang-names

locale-list:
	PYTHONPATH="." $(PYTHON) scripts/genlocalelist.py > locale-list

mini-wm: mini-wm.c
	gcc -o mini-wm mini-wm.c `pkg-config gtk+-x11-2.0 --cflags --libs`

_xkb.so: xkb.c
	gcc -Wall -o _xkb.o -O2 -fPIC -I$(PYTHONINCLUDE) `pkg-config --cflags gtk+-2.0` -c xkb.c 
	gcc -o _xkb.so -shared _xkb.o /usr/X11R6/$(LIBDIR)/libxkbfile.a `pkg-config --libs gtk+-2.0`

xmouse.so: xmouse.c
	gcc -Wall -o xmouse.o -fPIC -I/usr/X11R6/include -I$(PYTHONINCLUDE) -I $(PYTHONINCLUDE) -c xmouse.c 
	gcc -o xmouse.so -shared xmouse.o /usr/X11R6/$(LIBDIR)/libXxf86misc.a -L/usr/X11R6/$(LIBDIR) -lX11 -lXext

xutils.so: xutils.c
	gcc -ggdb -Wall -o xutils.o -fPIC -I/usr/X11R6/include -I$(PYTHONINCLUDE) -I $(PYTHONINCLUDE) -c xutils.c 
	gcc -o xutils.so -shared xutils.o -ggdb -L/usr/X11R6/$(LIBDIR) -lX11

depend:
	rm -f *.o *.so *.pyc
	for d in $(SUBDIRS); do make -C $$d depend; done

clean:
	rm -f *.o *.so *.pyc
	for d in $(SUBDIRS); do make -C $$d clean; done

subdirs:
	for d in $(SUBDIRS); do make -C $$d; [ $$? = 0 ] || exit 1; done

# this rule is a hack
install-python:
	cp -var $(PYFILES) $(DESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR) $(PYFILES)
	install -m 755 anaconda $(DESTDIR)/usr/bin/anaconda
	for d in installclasses isys iw textw; do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

install: 
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/sbin
	mkdir -p $(DESTDIR)/etc/rc.d/init.d
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	mkdir -p $(DESTDIR)/$(ANACONDADATADIR)

	install -m 755 anaconda $(DESTDIR)/usr/sbin/anaconda
	install -m 644 anaconda.conf $(DESTDIR)/$(ANACONDADATADIR)

	install -m 755 mini-wm $(DESTDIR)/usr/bin/mini-wm

	cp -var $(PYFILES) $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a lang-table $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a lang-names $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a locale-list $(DESTDIR)/$(ANACONDADATADIR)/locale-list
	cp -a lang-table-kon $(DESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR) $(PYFILES)
	cp -a *.so $(DESTDIR)/$(PYTHONLIBDIR)
	strip $(DESTDIR)/$(PYTHONLIBDIR)/*.so
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

CVSTAG=anaconda-$(subst .,_,$(VERSION)-$(RELEASE))
tag:
	@cvs tag -cR $(CVSTAG)
	@echo "Tagged as $(CVSTAG)"

archive: create-archive

src: create-archive
	@rpmbuild -ts --nodeps anaconda-$(VERSION).tar.bz2

snapsrc: create-snapshot
	@rpmbuild -ts --nodeps anaconda-$(VERSION).tar.bz2

create-snapshot:
	@rm -rf /tmp/anaconda
	@rm -rf /tmp/anaconda-$(VERSION)
	@tag=`cvs status Makefile | awk ' /Sticky Tag/ { print $$3 } '` 2> /dev/null; \
	[ x"$$tag" = x"(none)" ] && tag=HEAD; \
	[ x"$$TAG" != x ] && tag=$$TAG; \
	echo "*** Pulling off $$tag!"; \
	cd /tmp ; cvs -Q -d $(CVSROOT) export -r $$tag anaconda || echo "Um... export aborted."
	@cd /tmp/anaconda ; sed -e "s/@@VERSION@@/$(VERSION)/g" -e "s/@@RELEASE@@/$(SNAPRELEASE)/g" < anaconda.spec.in > anaconda.spec
	@mv /tmp/anaconda /tmp/anaconda-$(VERSION)
	@cd /tmp ; tar --bzip2 -cSpf anaconda-$(VERSION).tar.bz2 anaconda-$(VERSION)
	@rm -rf /tmp/anaconda-$(VERSION)
	@cp /tmp/anaconda-$(VERSION).tar.bz2 .
	@rm -f /tmp/anaconda-$(VERSION).tar.bz2
	@echo ""
	@echo "The final archive is in anaconda-$(VERSION).tar.bz2"

create-archive:
	make SNAPRELEASE=$(RELEASE) create-snapshot

pycheck:
	PYTHONPATH=isys:textw:iw:installclasses:booty:booty/edd pychecker *.py textw/*.py iw/*.py installclasses/*.py command-stubs/*-stub | grep -v "__init__() not called" 

pycheck-file:
	PYTHONPATH=.:isys:textw:iw:installclasses:booty:booty/edd pychecker $(CHECK) | grep -v "__init__() not called" 

PKGNAME=anaconda
local:
	@rm -rf ${PKGNAME}-$(VERSION).tar.gz
	@rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a $$dir ${PKGNAME}
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar --bzip2 -cvf $$dir/${PKGNAME}-$(VERSION).tar.bz2 ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.bz2"


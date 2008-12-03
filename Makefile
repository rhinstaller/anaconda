# Copyright (C) 1998-2002  Red Hat, Inc.
include Makefile.inc
VERSION := $(shell awk '/Version:/ { print $$2 }' anaconda.spec)
RELEASE := $(shell awk '/Release:/ { print $$2 }' anaconda.spec)
CVSROOT ?= ${CVSROOT:-$(shell cat CVS/Root 2>/dev/null)}

SUBDIRS = isys wlite stubs loader2 po \
	    textw utils scripts bootdisk installclasses \
	    iw pixmaps isomd5sum command-stubs ui
# fonts aren't on s390/s390x
ifneq (s390, $(ARCH))
ifneq (s390x, $(ARCH))
SUBDIRS += fonts
endif
endif

# gptsync only on x86 for mactels right now
ifeq (i386, $(ARCH))
SUBDIRS += gptsync
endif

CATALOGS = po/anaconda.pot

PYFILES = $(wildcard *.py)

all:  subdirs mini-wm xmouse.so xutils.so $(CATALOGS) lang-table lang-names

lang-names: lang-table
	PYTHONPATH="." $(PYTHON) scripts/getlangnames.py > lang-names

mini-wm: mini-wm.c
	gcc -o mini-wm mini-wm.c `pkg-config gtk+-x11-2.0 --cflags --libs`$(CFLAGS)

xmouse.so: xmouse.c
	gcc -Wall -o xmouse.o -fPIC -I/usr/X11R6/include -I$(PYTHONINCLUDE) -I $(PYTHONINCLUDE) -c xmouse.c $(CFLAGS)
	gcc -o xmouse.so -shared xmouse.o -L/usr/X11R6/$(LIBDIR) -lXxf86misc -lX11 -lXext

xutils.so: xutils.c
	gcc -ggdb -Wall -o xutils.o -fPIC -I/usr/X11R6/include -I$(PYTHONINCLUDE) -I $(PYTHONINCLUDE) -c xutils.c $(CFLAGS)
	gcc -o xutils.so -shared xutils.o -ggdb -L/usr/X11R6/$(LIBDIR) -lX11

depend:
	rm -f *.o *.so *.pyc
	for d in $(SUBDIRS); do make -C $$d depend; done

clean:
	rm -f *.o *.so *.pyc lang-names
	rm -rf docs/api
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
	install -m 755 mini-wm $(DESTDIR)/usr/bin/mini-wm

	cp -var $(PYFILES) $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a lang-table $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a lang-names $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a lang-table-kon $(DESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR) $(PYFILES)
	cp -a *.so $(DESTDIR)/$(PYTHONLIBDIR)
	strip $(DESTDIR)/$(PYTHONLIBDIR)/*.so
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

	mkdir -p $(DESTDIR)/usr/share/xml/comps/1.0
	install -m 0644 comps.dtd $(DESTDIR)/usr/share/xml/comps/1.0/comps.dtd

TAG=anaconda-$(VERSION)-$(RELEASE)
SRPMDIR=$(shell rpm --eval '%{_srcrpmdir}')
tag:
	git tag -a -m "Tag as $(TAG)" $(TAG)
	@echo "Tagged as $(TAG)"

ChangeLog:
	(GIT_DIR=.git git log > .changelog.tmp && mv .changelog.tmp ChangeLog; rm -f .changelog.tmp) || (touch ChangeLog; echo 'git directory not found: installing possibly empty changelog.' >&2)

archive: create-archive

src: create-archive
	@rpmbuild -ts --nodeps anaconda-$(VERSION).tar.bz2 || exit 1
	@rm -f anaconda-$(VERSION).tar.bz2

build: src
	@rm -rf /tmp/anaconda
	@mkdir /tmp/anaconda
	cd /tmp/anaconda ; cvs co common ; cd common ; ./cvs-import.sh -b RHEL-5 $(SRPMDIR)/anaconda-$(VERSION)-$(RELEASE).src.rpm
	@rm -rf /tmp/anaconda
	brew build $(COLLECTION) 'cvs://cvs.devel.redhat.com/cvs/dist?anaconda/RHEL-5#$(TAG)'

create-snapshot: ChangeLog tag
	@git archive --format=tar --prefix=$(PKGNAME)-$(VERSION)/ $(TAG) > anaconda-$(VERSION).tar
	@mkdir -p anaconda-$(VERSION)/
	@cp ChangeLog anaconda-$(VERSION)/
	@tar --append -f anaconda-$(VERSION).tar anaconda-$(VERSION)
	@bzip2 -f anaconda-$(VERSION).tar
	@rm -rf anaconda-$(VERSION)
	@echo "The final archive is in anaconda-$(VERSION).tar.bz2"

create-archive:
	make create-snapshot

pycheck:
	PYTHONPATH=isys:textw:iw:installclasses:booty:booty/edd pychecker *.py textw/*.py iw/*.py installclasses/*.py command-stubs/*-stub | grep -v "__init__() not called" 

pycheck-file:
	PYTHONPATH=.:isys:textw:iw:installclasses:booty:booty/edd pychecker $(CHECK) | grep -v "__init__() not called" 

PKGNAME=anaconda
local: clean
	@rm -rf ${PKGNAME}-$(VERSION).tar.gz
	@rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a $$dir ${PKGNAME}
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar --exclude .git --bzip2 -cvf $$dir/${PKGNAME}-$(VERSION).tar.bz2 ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.bz2"

api:
	doxygen docs/api.cfg

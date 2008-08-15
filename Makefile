# Copyright (C) 1998-2002  Red Hat, Inc.
include Makefile.inc
VERSION := $(shell awk '/Version:/ { print $$2 }' anaconda.spec)
RELEASE := $(shell awk '/Release:/ { print $$2 }' anaconda.spec)
CVSROOT ?= ${CVSROOT:-$(shell cat CVS/Root 2>/dev/null)}

SUBDIRS = isys wlite stubs loader2 po \
	    textw utils scripts bootdisk installclasses \
	    iw pixmaps isomd5sum command-stubs ui
# fonts aren't on s390/s390x
ifeq (,$(filter s390 s390x, $(ARCH)))
SUBDIRS += fonts
endif

ifneq (,$(filter ppc ppc64 i386 x86_64,$(ARCH)))
# we only do the liveinst bits on i386/x86_64 for now
SUBDIRS += liveinst
endif
ifneq (,$(filter i386 x86_64,$(ARCH)))
# gptsync only on x86 for mactels right now
SUBDIRS += gptsync
endif

PYCHECKERPATH=isys:textw:iw:installclasses:/usr/lib/booty:/usr/share/system-config-date
PYCHECKEROPTS=-F pycheckrc-for-anaconda

CATALOGS = po/anaconda.pot

PYFILES = $(wildcard *.py)

all:  subdirs mini-wm xutils.so $(CATALOGS) lang-table lang-names

lang-names: lang-table subdirs
	PYTHONPATH="." $(PYTHON) scripts/getlangnames.py > lang-names

mini-wm: mini-wm.c
	gcc -o mini-wm mini-wm.c `pkg-config gtk+-x11-2.0 --cflags --libs` $(CFLAGS) $(LDFLAGS)

xutils.so: xutils.c
	gcc -ggdb -Wall -o xutils.o -fno-strict-aliasing -fPIC -I/usr/X11R6/include -I$(PYTHONINCLUDE) -I $(PYTHONINCLUDE) -c xutils.c $(CFLAGS) `pkg-config --cflags gdk-2.0`
	gcc -o xutils.so -shared xutils.o -ggdb -L/usr/X11R6/$(LIBDIR) -lX11 `pkg-config --libs gdk-2.0` $(LDFLAGS)

depend:
	rm -f *.o *.so *.pyc
	for d in $(SUBDIRS); do make -C $$d depend; done

clean:
	rm -f *.o *.so *.pyc lang-names mini-wm
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
	./py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR) $(PYFILES)
	cp -a *.so $(DESTDIR)/$(PYTHONLIBDIR)
	strip $(DESTDIR)/$(PYTHONLIBDIR)/*.so
	for d in $(SUBDIRS); do make DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; [ $$? = 0 ] || exit 1; done

CVSTAG=anaconda-$(subst .,_,$(VERSION)-$(RELEASE))
SRPMDIR=$(shell rpm --eval '%{_srcrpmdir}')
tag:
	@cvs tag -cFR $(CVSTAG)
	@echo "Tagged as $(CVSTAG)"

archive: create-archive

src: create-archive
	@rpmbuild -ts --nodeps anaconda-$(VERSION).tar.bz2 || exit 1
	@rm -f anaconda-$(VERSION).tar.bz2

build: src
	@rm -rf /tmp/anaconda
	@mkdir /tmp/anaconda
	cd /tmp/anaconda ; cvs co common ; cd common ; ./cvs-import.sh $(SRPMDIR)/anaconda-$(VERSION)-$(RELEASE).src.rpm
	@rm -rf /tmp/anaconda
	koji build $(COLLECTION) 'cvs://cvs.fedoraproject.org/cvs/pkgs?devel/anaconda#$(CVSTAG)'

create-snapshot:
	@rm -rf /tmp/anaconda
	@rm -rf /tmp/anaconda-$(VERSION)
	@tag=`cvs status Makefile | awk ' /Sticky Tag/ { print $$3 } '` 2> /dev/null; \
	[ x"$$tag" = x"(none)" ] && tag=HEAD; \
	[ x"$$TAG" != x ] && tag=$$TAG; \
	cvsroot=`cat CVS/Root` 2>/dev/null; \
        echo "*** Pulling off $$tag from $$cvsroot!"; \
	cd /tmp ; cvs -z3 -Q -d $$cvsroot export -r $$tag anaconda || echo "Um... export aborted."
	@cd /tmp/anaconda ; curl -A "anaconda-build" -o docs/command-line.txt "http://fedoraproject.org/wiki/Anaconda/Options?action=raw"
	@cd /tmp/anaconda ; curl -A "anaconda-build" -o docs/kickstart-docs.txt "http://fedoraproject.org/wiki/Anaconda/Kickstart?action=raw"
	@mv /tmp/anaconda /tmp/anaconda-$(VERSION)
	@cd /tmp ; tar --bzip2 -cSpf anaconda-$(VERSION).tar.bz2 anaconda-$(VERSION)
	@rm -rf /tmp/anaconda-$(VERSION)
	@cp /tmp/anaconda-$(VERSION).tar.bz2 .
	@rm -f /tmp/anaconda-$(VERSION).tar.bz2
	@echo ""
	@echo "The final archive is in anaconda-$(VERSION).tar.bz2"

create-archive:
	make create-snapshot

pycheck:
	PYTHONPATH=$(PYCHECKERPATH) pychecker $(PYCHECKEROPTS) *.py textw/*.py iw/*.py installclasses/*.py | grep -v "__init__() not called" 

pycheck-file:
	PYTHONPATH=.:$(PYCHECKERPATH) pychecker $(PYCHECKEROPTS) $(CHECK) | grep -v "__init__() not called" 

PKGNAME=anaconda
local: clean
	@rm -rf ${PKGNAME}-$(VERSION).tar.gz
	@rm -rf /tmp/${PKGNAME}-$(VERSION) /tmp/${PKGNAME}
	@dir=$$PWD; cd /tmp; cp -a $$dir ${PKGNAME}
	@mv /tmp/${PKGNAME} /tmp/${PKGNAME}-$(VERSION)
	@dir=$$PWD; cd /tmp; tar --exclude CVS --exclude .git --exclude anaconda*.tar.bz2 --bzip2 -cvf $$dir/${PKGNAME}-$(VERSION).tar.bz2 ${PKGNAME}-$(VERSION)
	@rm -rf /tmp/${PKGNAME}-$(VERSION)
	@echo "The archive is in ${PKGNAME}-$(VERSION).tar.bz2"

api:
	doxygen docs/api.cfg

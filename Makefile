SUBDIRSHD = rpmmodule isys balkan libfdisk collage loader stubs po kudzu
SUBDIRS = $(SUBDIRSHD) gnome-map
BUILDONLYSUBDIRS = pump

TOPDIR = ../../..
DESTDIR = ../../../RedHat/instimage
CATALOGS = po/anaconda.pot
ALLSUBDIRS = $(BUILDONLYSUBDIRS) $(SUBDIRS) 

PYFILES = $(wildcard *.py) $(wildcard iw/*.py)

all: subdirs _xkb.so $(CATALOGS)

_xkb.so: xkb.c
	gcc -o _xkb.o -fPIC -I/usr/include/python1.5 -c xkb.c
	gcc -o _xkb.so -shared _xkb.o /usr/X11R6/lib/libxkbfile.a 

clean: 
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

subdirs:
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

install-hd: all
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/lib/python1.5/site-packages
	cp -a anaconda $(DESTDIR)/usr/bin
	cp -a *.py $(DESTDIR)/usr/lib/python1.5/site-packages
	mkdir -p $(DESTDIR)/usr/lib/python1.5/site-packages/iw
	cp -a iw/*.py $(DESTDIR)/usr/lib/python1.5/site-packages/iw
	cp -a *.py *.so $(DESTDIR)/usr/lib/python1.5/site-packages
	for d in $(SUBDIRSHD); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; done

install: all
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/lib/python1.5/site-packages
	mkdir -p $(DESTDIR)/usr/bin/iw
	cp -a anaconda $(DESTDIR)/usr/bin
	cp -a $(PYFILES) $(DESTDIR)/usr/lib/python1.5/site-packages
	./py-compile --basedir $(DESTDIR)/usr/lib/python1.5/site-packages $(PYFILES)
	cp -a iw/*.py $(DESTDIR)/usr/bin/iw
	cp -a *.py *.so $(DESTDIR)/usr/lib/python1.5/site-packages
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; done

SUBDIRS = rpmmodule isys balkan loader po libfdisk collage
BUILDONLYSUBDIRS = pump

TOPDIR = ../../..
DESTDIR = $(TOPDIR)/RedHat/instimage/usr/bin
CATALOGS = po/anaconda-text.pot
ALLSUBDIRS = $(SUBDIRS) $(BUILDONLYSUBDIRS)

all: subdirs _xkb.so $(CATALOGS)

_xkb.so: xkb.c
	gcc -o _xkb.so -shared -I/usr/include/python1.5 xkb.c

clean: 
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

subdirs:
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

install: all
	mkdir -p $(DESTDIR)
	mkdir -p $(DESTDIR)/iw
	cp -a anaconda *.py $(DESTDIR)
	cp -a iw/*.py $(DESTDIR)/iw
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d install; done

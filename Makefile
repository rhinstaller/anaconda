SUBDIRS = rpmmodule isys balkan po libfdisk collage loader
BUILDONLYSUBDIRS = pump

TOPDIR = ../../..
DESTDIR = $(TOPDIR)/RedHat/instimage
CATALOGS = po/anaconda-text.pot
ALLSUBDIRS = $(BUILDONLYSUBDIRS) $(SUBDIRS) 

all: subdirs _xkb.so $(CATALOGS)

_xkb.so: xkb.c
	gcc -o _xkb.o -fPIC -I/usr/include/python1.5 -c xkb.c
	gcc -o _xkb.so -shared _xkb.o /usr/X11R6/lib/libxkbfile.a 

clean: 
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

subdirs:
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

install: all
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/lib/python1.5/site-packages
	mkdir -p $(DESTDIR)/usr/bin/iw
	cp -a anaconda *.py $(DESTDIR)/usr/bin
	cp -a iw/*.py $(DESTDIR)/usr/bin/iw
	cp -a *.so $(DESTDIR)/usr/lib/python1.5/site-packages
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d install; done

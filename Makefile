include Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

SUBDIRSUNCFG = balkan help isys iw pixmaps po textw gnome-map
SUBDIRSHD = rpmmodule kudzu isys balkan libfdisk collage loader stubs po \
	    minislang textw utils
SUBDIRS = $(SUBDIRSHD) gnome-map iw help pixmaps
BUILDONLYSUBDIRS = pump

ifeq (i386, $(ARCH))
SUBDIRS += ddcprobe
SUBDIRSUNCFG += ddcprobe
endif


#
# TOPDIR         - ?
# DESTDIR        - destination for install image for install purposes
# UNCFGDESTDIR   - root of destination for install image for unconfig purposes
TOPDIR = ../../..
DESTDIR = ../../../RedHat/instimage
UNCFGDESTDIR = /

CATALOGS = po/anaconda.pot
ALLSUBDIRS = $(BUILDONLYSUBDIRS) $(SUBDIRS) 

PYFILES = $(wildcard *.py)

all: subdirs _xkb.so $(CATALOGS)

_xkb.so: xkb.c
	gcc -Wall -o _xkb.o -fPIC -I/usr/include/python1.5 `gtk-config --cflags gtk` -c xkb.c 
	gcc -o _xkb.so -shared _xkb.o /usr/X11R6/lib/libxkbfile.a `gtk-config --libs gtk`

clean:
	rm -f *.o *.so *.pyc
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

subdirs:
	for d in $(ALLSUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

install-unconfig: all
	@if [ "$(UNCFGDESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(UNCFGDESTDIR)/usr/sbin
	mkdir -p $(UNCFGDESTDIR)/$(PYTHONLIBDIR)
	cp -a anaconda $(UNCFGDESTDIR)/usr/sbin/anaconda-unconfig
	cp -var $(PYFILES) $(UNCFGDESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(UNCFGDESTDIR)/$(PYTHONLIBDIR) $(PYFILES)
	cp -a *.so $(UNCFGDESTDIR)/$(PYTHONLIBDIR)
	cp -a kudzu/kudzumodule.so $(UNCFGDESTDIR)/$(PYTHONLIBDIR)
	for d in $(SUBDIRSUNCFG); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(UNCFGDESTDIR); pwd` -C $$d install; done

install-hd: all
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a anaconda $(DESTDIR)/usr/bin
	cp -a *.py $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a *.so $(DESTDIR)/$(PYTHONLIBDIR)
	for d in $(SUBDIRSHD); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; done

install: all
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/bin
	cp -a anaconda $(DESTDIR)/usr/bin
	cp -var $(PYFILES) $(DESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(DESTDIR)/$(PYHTONLIBDIR) $(PYFILES)
	cp -a *.so $(DESTDIR)/$(PYTHONLIBDIR)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; done


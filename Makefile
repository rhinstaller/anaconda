include Makefile.inc

VERSION = 6.2.0

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

SUBDIRSRECFG = balkan help isys iw pixmaps po textw gnome-map
SUBDIRSHD = rpmmodule kudzu isys balkan libfdisk collage loader stubs po \
	    minislang textw utils
SUBDIRS = $(SUBDIRSHD) gnome-map iw help pixmaps
BUILDONLYSUBDIRS = pump

ifeq (i386, $(ARCH))
SUBDIRS += ddcprobe
SUBDIRSRECFG += ddcprobe
endif


#
# TOPDIR         - ?
# DESTDIR        - destination for install image for install purposes
# RECFGDESTDIR   - root of destination for install image for reconfig purposes
TOPDIR = ../../..
DESTDIR = ../../../RedHat/instimage
RECFGDESTDIR = /

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

install-reconfig: all
	@if [ "$(RECFGDESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi

	mkdir -p $(RECFGDESTDIR)/usr/sbin
	mkdir -p $(RECFGDESTDIR)/$(PYTHONLIBDIR)
	cp -a anaconda $(RECFGDESTDIR)/usr/sbin/anaconda-reconfig
	cp -var $(PYFILES) $(RECFGDESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(RECFGDESTDIR)/$(PYTHONLIBDIR) $(PYFILES)
	cp -a *.so $(RECFGDESTDIR)/$(PYTHONLIBDIR)
	cp -a kudzu/kudzumodule.so $(RECFGDESTDIR)/$(PYTHONLIBDIR)
	for d in $(SUBDIRSRECFG); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(RECFGDESTDIR); pwd` -C $$d install; done

install-hd: all
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)
	mkdir -p $(DESTDIR)/etc/rc.d/init.d

	cp -a anaconda $(DESTDIR)/usr/bin
	cp -a *.py $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a *.so $(DESTDIR)/$(PYTHONLIBDIR)
	cp -a reconfig.init $(DESTDIR)/etc/rc.d/init.d
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

create-archive:
	@rm -rf /tmp/anaconda
	@rm -rf /tmp/anaconda-reconfig-$(VERSION)
	@echo "WARNING WARNING WARNING: Pulling HEAD off - need to do tagging instead!"
	@cd /tmp ; cvs -Q -d $(CVSROOT) export -D "0 days ago"  anaconda || echo "Um... export aborted."
	@cd /tmp/anaconda ; sed -e "s/@@VERSION@@/$(VERSION)/g" < anaconda-reconfig.spec.in > anaconda-reconfig.spec
	@mv /tmp/anaconda /tmp/anaconda-reconfig-$(VERSION)
	@cd /tmp ; tar -czSpf anaconda-reconfig-$(VERSION).tar.gz anaconda-reconfig-$(VERSION)
	@rm -rf /tmp/anaconda-reconfig-$(VERSION)
	@cp /tmp/anaconda-reconfig-$(VERSION).tar.gz .
	@rm -f /tmp/anaconda-reconfig-$(VERSION).tar.gz
	@echo ""
	@echo "The final archive is in anaconda-reconfig-$(VERSION).tar.gz"

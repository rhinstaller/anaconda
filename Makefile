include Makefile.inc

VERSION = 6.2.1.8

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

SUBDIRSRECFG = balkan help isys iw pixmaps po textw gnome-map
SUBDIRSHD = rpmmodule kudzu balkan isys libfdisk collage loader stubs po \
	    minislang textw utils
SUBDIRS = $(SUBDIRSHD) gnome-map iw help pixmaps
BUILDONLYSUBDIRS = pump

ifeq (i386, $(ARCH))
SUBDIRS += ddcprobe
#SUBDIRSRECFG += ddcprobe
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

all: subdirs _xkb.so xmouse.so $(CATALOGS)

_xkb.so: xkb.c
	gcc -Wall -o _xkb.o -fPIC -I/usr/include/python1.5 `gtk-config --cflags gtk` -c xkb.c 
	gcc -o _xkb.so -shared _xkb.o /usr/X11R6/lib/libxkbfile.a `gtk-config --libs gtk`

xmouse.so: xmouse.c
	gcc -Wall -o xmouse.o -fPIC -I/usr/include/python1.5 -I /usr/include/python1.5 -c xmouse.c 
	gcc -o xmouse.so -shared xmouse.o /usr/X11R6/lib/libXxf86misc.a -L/usr/X11R6/lib -lX11 -lXext

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
	mkdir -p $(RECFGDESTDIR)/etc/rc.d/init.d
	mkdir -p $(RECFGDESTDIR)/$(PYTHONLIBDIR)

	cp -a reconfig.init $(RECFGDESTDIR)/etc/rc.d/init.d/reconfig
	cp -a anaconda $(RECFGDESTDIR)/usr/sbin/anaconda
	cp -var $(PYFILES) $(RECFGDESTDIR)/$(PYTHONLIBDIR)
	cp -a lang-table $(RECFGDESTDIR)/$(PYTHONLIBDIR)
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

	install anaconda $(DESTDIR)/usr/bin
	install *.py $(DESTDIR)/$(PYTHONLIBDIR)
	install *.so $(DESTDIR)/$(PYTHONLIBDIR)
	for d in $(SUBDIRSHD); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; done

install: all
	@if [ "$(DESTDIR)" = "" ]; then \
		echo " "; \
		echo "ERROR: A destdir is required"; \
		exit 1; \
	fi
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)
	install anaconda $(DESTDIR)/usr/bin
	install raidstart-stub $(DESTDIR)/$(PYTHONLIBDIR)
	install raidstop-stub $(DESTDIR)/$(PYTHONLIBDIR)
	install $(PYFILES) $(DESTDIR)/$(PYTHONLIBDIR)
	install lang-table $(DESTDIR)/$(PYTHONLIBDIR)
	./py-compile --basedir $(DESTDIR)/$(PYHTONLIBDIR) $(PYFILES)
	install *.so $(DESTDIR)/$(PYTHONLIBDIR)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) DESTDIR=`cd $(DESTDIR); pwd` -C $$d install; done

create-archive:
	@rm -rf /tmp/anaconda
	@rm -rf /tmp/anaconda-$(VERSION)
	@echo "WARNING WARNING WARNING: Pulling HEAD off - need to do tagging instead!"
	@cd /tmp ; cvs -Q -d $(CVSROOT) export -r HEAD anaconda || echo "Um... export aborted."
	@cd /tmp/anaconda ; rm isys/modutils/modutils.spec; rm pump/pump.spec 
	@cd /tmp/anaconda; rm kudzu/kudzu.spec
	@cd /tmp/anaconda ; sed -e "s/@@VERSION@@/$(VERSION)/g" < anaconda.spec.in > anaconda.spec
	@mv /tmp/anaconda /tmp/anaconda-$(VERSION)
	@cd /tmp ; tar -czSpf anaconda-$(VERSION).tar.gz anaconda-$(VERSION)
	@rm -rf /tmp/anaconda-$(VERSION)
	@cp /tmp/anaconda-$(VERSION).tar.gz .
	@rm -f /tmp/anaconda-$(VERSION).tar.gz
	@echo ""
	@echo "The final archive is in anaconda-$(VERSION).tar.gz"

SUBDIRS = rpmmodule isys balkan loader po
TOPDIR = ../../..
DESTDIR = $(TOPDIR)/RedHat/instimage/usr/bin
CATALOGS = po/anaconda-text.pot

all: subdirs $(CATALOGS)

clean: 
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

subdirs:
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

install: all
	mkdir -p $(DESTDIR)
	mkdir -p $(DESTDIR)/iw
	cp -a anaconda *.py $(DESTDIR)
	cp -a iw/*.py $(DESTDIR)/iw
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d install; done

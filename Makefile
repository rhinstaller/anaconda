SUBDIRS = rpmmodule isys balkan loader
TOPDIR = ../../..
DESTDIR = $TOPDIR/RedHat/instimage/usr/bin

all: subdirs

clean: 
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

subdirs:
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

install: all
	mkdir -p $(DESTDIR)
	cp -a anaconda comps.py gui.py image.py text.py $(DESTDIR)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d install; done

SUBDIRS = rpmmodule isys balkan loader
TOPDIR = ../../..
DESTDIR = $TOPDIR/RedHat/instimage/usr/bin

all: subdirs

clean: 
	for d in $(SUBDIRS); do make -C $$d clean; done

subdirs:
	for d in $(SUBDIRS); do make -C $$d; done

install: all
	mkdir -p $(DESTDIR)
	cp -a anaconda comps.py gui.py image.py text.py $(DESTDIR)
	for d in $(SUBDIRS); do make -C $$d install; done

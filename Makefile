SUBDIRS = rpmmodule isys balkan loader

DESTDIR = ../../../RedHat/instimage/usr/bin

all: subdirs

clean: 
	for d in $(SUBDIRS); do \
	(cd $$d; $(MAKE) clean) \
	  || case "$(MFLAGS)" in *k*) fail=yes;; *) exit 1;; esac;\
        done && test -z "$$fail"

subdirs:
	for d in $(SUBDIRS); do \
	(cd $$d; $(MAKE)) \
	  || case "$(MFLAGS)" in *k*) fail=yes;; *) exit 1;; esac;\
        done && test -z "$$fail"

install: all
	mkdir -p $(DESTDIR)
	cp -a anaconda comps.py gui.py image.py text.py $(DESTDIR)
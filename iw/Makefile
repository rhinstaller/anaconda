include ../Makefile.inc

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/iw
	cp -a *.py $(DESTDIR)/$(PYTHONLIBDIR)/iw
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/iw $(DESTDIR)/$(PYTHONLIBDIR)/iw/*.py


include ../Makefile.inc

ifeq (i386, $(ARCH))
CLASSES = $(shell ls *.py)
else
CLASSES = $(shell ls *.py | grep -v laptop)
endif

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/installclasses
	install $(CLASSES) $(DESTDIR)/$(PYTHONLIBDIR)/installclasses
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/installclasses $(DESTDIR)/$(PYTHONLIBDIR)/installclasses/*.py

clean:
	rm -f *.o *.so *.pyc

depend:

include ../Makefile.inc

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/iw
	install *.py $(DESTDIR)/$(PYTHONLIBDIR)/iw
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/iw $(DESTDIR)/$(PYTHONLIBDIR)/iw/*.py

clean:
	rm -f *.o *.so *.pyc

depend:

include ../Makefile.inc

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/installclasses
	install *.py $(DESTDIR)/$(PYTHONLIBDIR)/installclasses
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/installclasses $(DESTDIR)/$(PYTHONLIBDIR)/installclasses/*.py

clean:
	rm -f *.o *.so *.pyc

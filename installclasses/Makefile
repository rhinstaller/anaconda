include ../Makefile.inc

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/installclass
	install *.py $(DESTDIR)/$(PYTHONLIBDIR)/installclass
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/installclass $(DESTDIR)/$(PYTHONLIBDIR)/installclass/*.py

clean:
	rm -f *.o *.so *.pyc

include ../Makefile.inc

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/textw
	cp -a *.py $(DESTDIR)/$(PYTHONLIBDIR)/textw
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/textw $(DESTDIR)/$(PYTHONLIBDIR)/textw/*.py

clean:
	rm -f *.o *.so *.pyc

include ../Makefile.inc

all:
	$(PYTHON) setup.py build --build-platlib=`pwd`

install:
	$(PYTHON) setup.py install --install-lib=$(DESTDIR)/$(PYTHONLIBDIR)

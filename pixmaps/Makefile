include ../Makefile.inc

RNOTES_LANGS= de en fr it

all:
	@echo "nothing to do"

install: 
	mkdir -p $(DESTDIR)/$(ANACONDADATADIR)/pixmaps
	install *.png $(DESTDIR)/$(ANACONDADATADIR)/pixmaps

	for i in $(RNOTES_LANGS); do \
	  mkdir -p $(DESTDIR)/$(ANACONDADATADIR)/pixmaps/rnotes/$$i; \
	  install rnotes/$$i/*.png $(DESTDIR)/$(ANACONDADATADIR)/pixmaps/rnotes/$$i; \
	done

depend:

include ../Makefile.inc

all:

install:
	install -m 755 upd-instroot $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 mk-images* $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 buildinstall $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 splitdistro $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 scrubtree $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 pythondeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 pkgorder $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 check-repository.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 getkeymaps $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 makestamp.py $(DESTDIR)/$(RUNTIMEDIR)

depend:

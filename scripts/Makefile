include ../Makefile.inc

all:

install:
	install -m 755 upd-instroot $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 mk-images* $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 mk-rescueimage* $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 buildinstall $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 splittree.py $(DESTDIR)/$(RUNTIMEDIR)
#	install -m 755 splitdistro $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 scrubtree $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 pkgorder $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 getkeymaps $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 makestamp.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 fixmtime.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 yumcache $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 pyrc.py $(DESTDIR)/$(RUNTIMEDIR)

depend:

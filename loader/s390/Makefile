CFLAGS=-Wall -O2
LDLIBS=-lnewt
PACKAGE=installer
VERSION=$(shell cat installer.spec | grep Version: | sed 's/Version: //g')
VERNAME=$(PACKAGE)-$(VERSION)

SOURCES=dasdformat.c mountpoint.c netsetup.c pkgsrc.c pkgselect.c Makefile installer.spec common.h
APPS=dasdformat mountpoint netsetup pkgsrc pkgselect

all:	$(APPS)
	strip $(APPS)

dasdformat: dasdformat.c
mountpoint: mountpoint.c
netsetup: netsetup.c
pkgsrc: pkgsrc.c
pkgselect: pkgselect.c

install: $(APPS)
	mkdir -p $(DESTDIR)/usr/bin
	install $(APPS) $(DESTDIR)/usr/bin

clean:
	rm -f $(APPS)
	rm -rf $(PACKAGE).tar.gz $(PACKAGE).tar
	rm -rf $(VERNAME)-1.src.rpm

tar:
	rm -rf $(PACKAGE)
	rm -rf $(VERNAME).tar
	mkdir $(PACKAGE) 2>/dev/null
	cp $(SOURCES) $(PACKAGE)/
	tar cvf $(VERNAME).tar $(PACKAGE)
	rm -rf $(PACKAGE)

tgz:	tar
	rm -rf $(VERNAME).tar.gz
	gzip $(VERNAME).tar

srpm:	tgz
	rpmbuild --define "_srcrpmdir `pwd`" -ts $(VERNAME).tar.gz
	rm -rf $(VERNAME).tar.gz

rpm:	srpm
	rpm --rebuild $(VERNAME)-1.src.rpm
	cp ~/rpms/s390/$(VERNAME)-1.*.rpm ../


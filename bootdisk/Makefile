include ../Makefile.inc

all:

install:
	rm -rf $(DESTDIR)/$(RUNTIMEDIR)/boot
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)/boot
	if [ -d $(ARCH) ]; then \
	    cp -av $(ARCH)/[a-z]* $(DESTDIR)/$(RUNTIMEDIR)/boot; \
	fi

depend:

include ../Makefile.inc

all:

depend:

install:
	if [ -f keymaps-$(ARCH) ]; then install -m 644 keymaps-$(ARCH) $(DESTDIR)/$(RUNTIMEDIR)/keymaps-override-$(ARCH) ; fi

clean:

i386:
	./updkmaps i386

alpha:
	./updkmaps alpha

sparc:
	./updkmaps sparc

s390:
	./updkmaps s390

s390x:
	./updkmaps s390

ppc:
	./updkmaps ppc

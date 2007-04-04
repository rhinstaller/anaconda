include ../Makefile.inc

all:

depend:

install:
	if [ -f keymaps-$(ARCH) ]; then install -m 644 keymaps-$(ARCH) $(DESTDIR)/$(RUNTIMEDIR)/keymaps-override-$(ARCH) ; fi

clean:

alpha:
	./updkmaps alpha

i386:
	./updkmaps i386

ia64:
	./updkmaps ia64

ppc:
	./updkmaps ppc

s390:
	./updkmaps s390

s390x:
	./updkmaps s390x

sparc:
	./updkmaps sparc

x86_64:
	./updkmaps x86_64

include ../Makefile.inc

LIBBZ = libbz2.so.1
LIBUTF8 = libunicode-lite.so.1

TARGETS= $(LIBUTF8)

ifneq (ia64, $(ARCH))
TARGETS += $(LIBBZ)
endif

all:	$(TARGETS)

$(LIBBZ):   bzip.c
	gcc -fPIC -shared -o $@ $<

$(LIBUTF8): unicode-lite.c
	gcc -fPIC -shared -o $@ $< -lwlite

clean:
	rm -f *.so.* *.o

install:
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	for lib in $(TARGETS) ; do install $$lib $(DESTDIR)/$(RUNTIMEDIR) ; done

depend:

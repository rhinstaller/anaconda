include ../Makefile.inc

LIBUTF8 = libunicode-lite.so.1

TARGETS= $(LIBUTF8)

all:	$(TARGETS)

$(LIBUTF8): unicode-lite.c
	gcc -fPIC -shared -o $@ $< -lwlite -D_FORTIFY_SOURCE=2

clean:
	rm -f *.so.* *.o

install:
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	for lib in $(TARGETS) ; do install $$lib $(DESTDIR)/$(RUNTIMEDIR) ; done

depend:

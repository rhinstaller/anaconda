include ../Makefile.inc

LIBBZ = libbz2.so.1
LIBUTF8 = libunicode-lite.so.1

all:	$(LIBBZ) $(LIBUTF8)

$(LIBBZ):   bzip.c
	gcc -fPIC -shared -o $@ $<

$(LIBUTF8): unicode-lite.c
	gcc -fPIC -shared -o $@ $< -lwlite

clean:
	rm -f *.so.* *.o

install:
	install $(LIBBZ) $(DESTDIR)/$(RUNTIMEDIR)
	install $(LIBUTF8) $(DESTDIR)/$(RUNTIMEDIR)

depend:

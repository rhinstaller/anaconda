include ../Makefile.inc

LIBUTF8 = libunicode-lite.so.1

OBJECTS = unicode-lite.o

TARGETS= $(LIBUTF8)

all:	$(TARGETS) libunicode-lite.a

CFLAGS += -I../wlite/

$(LIBUTF8): unicode-lite.c
	gcc -fPIC -shared -I../wlite/ -o $@ $< -D_FORTIFY_SOURCE=2 ../wlite/libwlite.a

libunicode-lite.a: libunicode-lite.a($(OBJECTS))

clean:
	rm -f *.so.* *.o *.a

install:
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	for lib in $(TARGETS) ; do install $$lib $(DESTDIR)/$(RUNTIMEDIR) ; done

depend:

include ../Makefile.inc

OBJS = sldisply.o slerr.o slgetkey.o slmisc.o slsignal.o slsmg.o    \
	sltermin.o slutty.o slkanji.o
SOBJS = $(patsubst %.o,%.lo,$(OBJS))
DOBJS = $(patsubst %.o,%.do,$(OBJS))

CFLAGS = -Os

STATICLIB=libslang.a($(OBJS))
ifeq (i386, $(ARCH))
STATICLIB=libslang-diet.a($(DOBJS))
endif
ifeq (ppc, $(ARCH))
STATICLIB=libslang-diet.a($(DOBJS))
endif

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	libslang.so $(STATICLIB)

%.lo: %.c
	$(CC) -c $(CFLAGS) -fPIC -o $@ $<

%.do: %.c
	diet $(CC) -c $(CFLAGS) -o $@ $<

libslang.so: $(SOBJS)
	gcc -o $@ -shared -Wl,-soname,libslang.so.1 $(SOBJS)

clean:
	rm -f *.o *.so *.lo *.do libslang.so libslang.a libslang-diet.a

install:    libslang.so
	install -s libslang.so $(DESTDIR)/$(RUNTIMEDIR)/libslang.so.1
	ln -s libslang.so.1 $(DESTDIR)/$(RUNTIMEDIR)/libslang-j.so.1

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

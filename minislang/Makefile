include ../Makefile.inc

OBJS = sldisply.o slerr.o slgetkey.o slmisc.o slsignal.o slsmg.o    \
	sltermin.o slutty.o slkanji.o
SOBJS = $(patsubst %.o,%.lo,$(OBJS))

CFLAGS = -Os

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	libslang.so libslang.a($(OBJS))

%.lo: %.c
	$(CC) -c $(CFLAGS) -fPIC -o $@ $<

libslang.so: $(SOBJS)
	gcc -o $@ -shared -Wl,-soname,libslang.so.1 $(SOBJS)

clean:
	rm -f *.o *.so *.lo libslang.so libslang.a

install:    libslang.so
	install -s libslang.so $(DESTDIR)/$(RUNTIMEDIR)/libslang.so.1
	ln -s libslang.so.1 $(DESTDIR)/$(RUNTIMEDIR)/libslang-j.so.1

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

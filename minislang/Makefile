include ../Makefile.inc

OBJS = sldisply.o slerr.o slgetkey.o slmisc.o slsignal.o slsmg.o    \
	sltermin.o slutty.o slkanji.o

CFLAGS = -fPIC -O2

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	libslang.so libslang.a($(OBJS))

libslang.so:	$(OBJS)
	gcc -o $@ -shared -Wl,-soname,libslang.so.1 $(OBJS)

clean:
	rm -f *.o libslang.so

install:    libslang.so
	install -s libslang.so $(DESTDIR)/$(RUNTIMEDIR)/libslang.so.1
	ln -s libslang.so.1 $(DESTDIR)/$(RUNTIMEDIR)/libslang-j.so.1

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

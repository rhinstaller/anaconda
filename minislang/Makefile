include ../Makefile.inc

OBJS = sldisply.o slerr.o slgetkey.o slmisc.o slsignal.o slsmg.o    \
	sltermin.o slutty.o

CFLAGS = -fPIC

all:	libslang.so

libslang.so:	$(OBJS)
	gcc -o $@ -shared -Wl,-soname,libslang.so.1 $(OBJS)

clean:
	rm -f *.o libslang.so

install:    libslang.so
	install -s libslang.so $(DESTDIR)/$(RUNTIMEDIR)/libslang.so.1

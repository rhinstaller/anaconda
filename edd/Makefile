include ../Makefile.inc

CFLAGS=-Wall -O -g -fpic -I/usr/include/python1.5# -DDEBUG

#libedd.a(edd.o lrmi.o)
TARGETS=eddmodule.so 

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: $(TARGETS)

install: all
	install eddmodule.so $(DESTDIR)/$(PYTHONLIBDIR)

edd: lrmi.c edd.c
	gcc -DDEBUG -o edd lrmi.c edd.c

eddmodule.so: pyedd.c # edd.o lrmi.o
	gcc -c -o pyedd.o -fpic pyedd.c $(CFLAGS)
	gcc -shared -g -o $@ pyedd.o # edd.o lrmi.o

clean:
	rm -f *.o *.so *~ core

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

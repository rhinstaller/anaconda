CFLAGS=-Wall -O -g -fpic -I/usr/include/python1.5# -DDEBUG

TARGETS=eddmodule.so libedd.a(edd.o lrmi.o)

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: $(TARGETS)

edd: lrmi.c edd.c
	gcc -DDEBUG -o edd lrmi.c edd.c

eddmodule.so: pyedd.c edd.o lrmi.o
	gcc -c -o pyedd.o -fpic pyedd.c $(CFLAGS)
	gcc -shared -g -o $@ pyedd.o edd.o lrmi.o

clean:
	rm -f *.o *.so *~ core

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

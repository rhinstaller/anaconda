CFLAGS=-Wall -O -g -fpic# -DDEBUG

TARGETS=eddmodule.so

all: $(TARGETS)

edd: lrmi.c edd.c
	gcc -DDEBUG -o edd lrmi.c edd.c

eddmodule.so: pyedd.c edd.o lrmi.o
	gcc -c -o pyedd.o -fpic pyedd.c -I/usr/include/python1.5
	gcc -shared -g -o $@ pyedd.o edd.o lrmi.o

clean:
	rm -f *.o *.so *~ core

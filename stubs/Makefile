include ../Makefile.inc

LIBBZ = libbz2.so.1

all:	$(LIBBZ)

$(LIBBZ):   bzip.c
	gcc -fPIC -shared -o $(LIBBZ) bzip.c

clean:
	rm -f *.so.* *.o

install:
	install $(LIBBZ) $(DESTDIR)/$(RUNTIMEDIR)

depend:

all:	libbz2.so.0

libbz2.so.0:	bzip.c
	gcc -fPIC -shared -o libbz2.so.0 bzip.c

clean:
	rm -f *.so.* *.o

install:
	install libbz2.so.0 $(DESTDIR)/usr/lib

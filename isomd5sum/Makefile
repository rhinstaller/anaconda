include ../Makefile.inc

all:
	gcc -c -O -g -D_FILE_OFFSET_BITS=64 md5.c
	gcc -c -O -g -D_FILE_OFFSET_BITS=64 libimplantisomd5.c
	gcc -O -g -D_FILE_OFFSET_BITS=64 -o  implantisomd5 implantisomd5.c libimplantisomd5.o  md5.o -lm -lpopt
	gcc -c -O -g -D_FILE_OFFSET_BITS=64 libcheckisomd5.c
	gcc -O -g -D_FILE_OFFSET_BITS=64 -o checkisomd5 checkisomd5.c libcheckisomd5.o md5.o -lm

install:
	install -m 755 implantisomd5 $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 checkisomd5 $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f *.o
	rm -f implantisomd5 checkisomd5 

depend:

include ../Makefile.inc

all:	
	gcc -c -O -g -fPIC  -D_FILE_OFFSET_BITS=64 md5.c
	gcc -c -O -g -fPIC -D_FILE_OFFSET_BITS=64 libimplantisomd5.c
	gcc -O -g -D_FILE_OFFSET_BITS=64 -o  implantisomd5 implantisomd5.c libimplantisomd5.o  md5.o -lm -lpopt
	gcc -c -O -g -fPIC -D_FILE_OFFSET_BITS=64 libcheckisomd5.c
	gcc -O -g -D_FILE_OFFSET_BITS=64 -o checkisomd5 checkisomd5.c libcheckisomd5.o md5.o -lm

	gcc -c -O -g -fPIC -o pyisomd5sum.lo pyisomd5sum.c -I$(PYTHONINCLUDE)
	gcc -shared -g -o pyisomd5sum.so -fpic pyisomd5sum.lo libcheckisomd5.o libimplantisomd5.o md5.o

install:
	install -m 755 implantisomd5 $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 checkisomd5 $(DESTDIR)/$(RUNTIMEDIR)
	install -s pyisomd5sum.so $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f *.o *.lo *.so *.pyc
	rm -f implantisomd5 checkisomd5 

depend:

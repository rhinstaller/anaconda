include ../Makefile.inc

all:
	gcc -c -O -g md5.c
	gcc -O -g -o implantisomd5 implantisomd5.c md5.o -lm
	gcc -O -g -o checkisomd5 checkisomd5.c md5.o -lm

install:
	install -m 755 implantisomd5 $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 checkisomd5 $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f *.o
	rm -f implantisomd5 checkisomd5 

depend:

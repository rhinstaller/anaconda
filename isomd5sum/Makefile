include ../Makefile.inc

all:
	gcc -c -O -g md5.c
	gcc -O -g -o implantisomd5 implantisomd5.c md5.o -lm
#	gcc -O -g -o checkisomd5 -DTESTING checkisomd5.c md5.o -lm
#	gcc -O -g -c checkisomd5.c
#	gcc -O -g -o newtcheckiso newtcheckiso.c checkisomd5.o md5.o -lm -lnewt

install:
	install -m 755 implantisomd5 $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f *.o
	rm -f implantisomd5 checkisomd5 

depend:

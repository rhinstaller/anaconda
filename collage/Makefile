CFLAGS = -Wall -g -I/usr/include/rpm
LDFLAGS = -g
LOADLIBES = -L../isys -lz -lisys -lresolv -lrpm -lbz2 -lpopt

all:	collage

collage:	collage.o commands.o idmap.o ls.o

install:
	install -s collage $(DESTDIR)/usr/bin
	(a=`pwd`; cd $(DESTDIR)/usr/bin; ./collage | 	\
		$$a/mkcollagelinks collage)

clean:
	rm -f collage *.o

CFLAGS = -Wall -g 
LDFLAGS = -g
LOADLIBES = -L../isys -lz -lisys -lresolv -lpopt

all:	collage

collage:	collage.o commands.o idmap.o ls.o

install:
	install -s collage $(DESTDIR)/usr/bin
	(a=`pwd`; cd $(DESTDIR)/usr/bin; ./collage | 	\
		$$a/mkcollagelinks collage)

clean:
	rm -f collage *.o

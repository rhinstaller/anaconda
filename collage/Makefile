CFLAGS = -Wall -g
LDFLAGS = -g
LOADLIBES = -L../isys -lpopt -lz -lisys -lresolv -lrpm

all:	collage

collage:	collage.o commands.o idmap.o ls.o

install:
	install -s collage $(DESTDIR)/usr/bin
	(a=`pwd`; cd $(DESTDIR)/usr/bin; ./collage | 	\
		$$a/mkcollagelinks collage)

CFLAGS = -Wall -g 
LDFLAGS = -g
LOADLIBES = -L../isys -lz -lisys -lresolv -lpopt

all:	collage

collage:	collage.o commands.o idmap.o ls.o

install:
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	install -s collage $(DESTDIR)/$(RUNTIMEDIR)
	install mkcollagelinks $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f collage *.o

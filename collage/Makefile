include ../Makefile.inc

CFLAGS = -Wall -g -O2
LDFLAGS = -g
LOADLIBES = -L../isys -lz -lisys -lresolv -lpopt

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	collage

collage:	collage.o commands.o idmap.o ls.o

install:
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	install -s collage $(DESTDIR)/$(RUNTIMEDIR)
	install mkcollagelinks $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f collage *.o

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

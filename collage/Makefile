include ../Makefile.inc

CFLAGS = -Wall -g -O2
LDFLAGS = -g
LOADLIBES = -L../isys -L../isys/gzlib -lisys -lgunzip -lresolv -lz

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	collage

collage:	collage.o commands.o mount_by_label.o

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

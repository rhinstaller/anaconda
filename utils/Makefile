include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

LOADLIBES =  -L../isys -lisys -lpopt
CFLAGS = -Wall -g -I/usr/include/rpm
LDFLAGS = -g -static
MODDEPS = moddeps

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	modlist $(MODDEPS) genhdlist snarffont mapshdr readmap

moddeps: moddeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o ../loader/modules.o \
            $(LOADLIBES) \
	    ../isys/modutils/insmod/libmodutils.a    \
	    ../isys/modutils/util/libutil.a          \
	    ../isys/modutils/obj/libobj.a -lrpm -lrpmio -lbz2 -lz -lpopt

genhdlist: genhdlist.c
	$(CC) $(LDFLAGS) $(CFLAGS) -o genhdlist genhdlist.c -lrpm -lrpmio \
	-lbz2 -lz -lpopt -ldb-3.0 -ldb1

depends:

install: all
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 -s genhdlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimpcitable $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 -s moddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 filtermoddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 -s modlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 -s checkcards.py $(DESTDIR)/$(RUNTIMEDIR)

#
# removed genhdlist from clean line so it will be distributed on CDROM image
#
clean:	
	rm -f modlist moddeps snarffont *.o 

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

ISYSLIB=isys

LOADLIBES =  -L../isys -l$(ISYSLIB) -lpopt
CFLAGS = -Wall -g -I..
RPMCFLAGS = -I/usr/include/rpm
LDFLAGS = -g -static
MODDEPS = moddeps

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	modlist $(MODDEPS) genhdlist snarffont mapshdr readmap

modlist:    modlist.o 

moduledeps.o: ../loader/moduledeps.c
	cp ../loader/moduledeps.c ./
	$(CC) $(CFLAGS) -I../loader -c moduledeps.c

moddeps: moddeps.o moduledeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o moduledeps.o \
            $(LOADLIBES) -lresolv \
	    -lmodutils -lmodutilobj -lmodutilutil  \
	    -lpopt -lbz2

genhdlist: genhdlist.c hash.c
	$(CC) $(LDFLAGS) $(CFLAGS) $(RPMCFLAGS) -o genhdlist genhdlist.c hash.c -lrpm -lrpmdb -lrpmio \
	-lbz2 -lz -lpopt 

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
	rm -f modlist moddeps snarffont genhdlist mapshdr readmap *.o 

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

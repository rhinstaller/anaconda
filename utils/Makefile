include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

ISYSLIB=isys

LOADLIBES =  -L../isys -l$(ISYSLIB) -lpopt
CFLAGS = -Wall -g -I.. -I/usr/include/rpm-4.0.4 -I../loader
LDFLAGS = -g -static
MODDEPS = moddeps

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	modlist $(MODDEPS) snarffont mapshdr readmap

modlist:    modlist.o 

moduledeps.o: ../loader/moduledeps.c
	cp ../loader/moduledeps.c ./
	$(CC) $(CFLAGS) -c moduledeps.c

moddeps: moddeps.o moduledeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o moduledeps.o \
            $(LOADLIBES) -lresolv \
	    -lmodutils -lmodutilobj -lmodutilutil  \
	    -lpopt -lbz2

md5.o: md5.c md5.h
	gcc -c -O -g md5.c

genhdlist: genhdlist.c hash.c
	$(CC) $(LDFLAGS) $(CFLAGS) -o genhdlist genhdlist.c hash.c -lrpm-4.0.4 -lrpmdb-4.0.4 -lrpmio-4.0.4 \
	-lbz2 -lz -lpopt 

depends:

install: all
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
#	install -m755 genhdlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimpcitable $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 moddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 filtermoddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 modlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 checkcards.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 readmap $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 mapshdr $(DESTDIR)/$(RUNTIMEDIR)

clean:	
	rm -f modlist moddeps snarffont genhdlist mapshdr readmap *.o 

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

ISYSLIB=isys

LOADERDIR = ../loader2
LOADLIBES =  -lpopt
CFLAGS = -Wall -g -I.. -I$(LOADERDIR)
RPMCFLAGS = $(CFLAGS) -I/usr/include/rpm
LDFLAGS = -g -static

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	modlist moddeps snarffont mapshdr readmap genhdlist

modlist: modlist.o moduleinfo.o
	$(CC) $(LDFLAGS) -o modlist modlist.o moduleinfo.o $(LOADLIBES)

moduleinfo.o: $(LOADERDIR)/moduleinfo.c
	cp $(LOADERDIR)/moduleinfo.c ./
	$(CC) $(CFLAGS) -c moduleinfo.c

moduledeps.o: $(LOADERDIR)/moduledeps.c
	cp $(LOADERDIR)/moduledeps.c ./
	$(CC) $(CFLAGS) -c moduledeps.c

moddeps: moddeps.o moduledeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o moduledeps.o \
            $(LOADLIBES) -lresolv \
	    -lmodutils -lmodutilobj -lmodutilutil  \
	    -lpopt -lbz2

md5.o: md5.c md5.h
	gcc -c -O -g md5.c

genhdlist: genhdlist.c hash.c
	$(CC) $(LDFLAGS) $(RPMCFLAGS) -o genhdlist genhdlist.c hash.c \
	-lrpm -lrpmdb -lrpmio -lbz2 -lz -lpopt -lelf -lpthread

depends:

install: all
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 genhdlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimpcitable $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 moddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 filtermoddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 modlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 checkcards.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 readmap $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 mapshdr $(DESTDIR)/$(RUNTIMEDIR)

clean:	
	rm -f modlist moddeps snarffont genhdlist mapshdr readmap \
	moduledeps.c moduleinfo.c *.o

depend:
	$(CPP) -M $(RPMCFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

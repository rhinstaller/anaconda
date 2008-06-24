include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

ISYSLIB=isys

LOADERDIR = ../loader2
LOADLIBES =  -lpopt
CFLAGS = -Wall -g -I.. -I$(LOADERDIR) -Werror
RPMCFLAGS = $(CFLAGS) -I/usr/include/rpm
LDFLAGS = -g

UTILS = modlist moddeps snarffont mapshdr readmap genhdlist
ifeq (s390, $(ARCH))
UTILS += geninitrdsz
endif
ifeq (s390x, $(ARCH))
UTILS += geninitrdsz
endif

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all:	$(UTILS)

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
            $(LOADLIBES) -lresolv -lpopt -lbz2

md5.o: md5.c md5.h
	gcc -c -O -g md5.c

geninitrdsz: geninitrdsz.c
	$(CC) $(CFLAGS) -o $@ $<

genhdlist: genhdlist.c hash.c
	$(CC) $(LDFLAGS) $(RPMCFLAGS) -o genhdlist genhdlist.c hash.c \
	-lrpm -lrpmdb -lrpmio -lbz2 -lz -lpopt -lelf -lpthread -lbeecrypt

depends:

install: all
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 genhdlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimpcitable $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimmodmap $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimpciids $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimusbmap $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 moddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 filtermoddeps $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 modlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 checkcards.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 readmap $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 mapshdr $(DESTDIR)/$(RUNTIMEDIR)
	if [ -x geninitrdsz ]; then \
		install -m755 geninitrdsz $(DESTDIR)/$(RUNTIMEDIR) ; \
	fi

clean:	
	rm -f modlist moddeps snarffont genhdlist mapshdr readmap \
	geninitrdsz moduledeps.c moduleinfo.c .depend *.o

depend:
	$(CPP) -M $(RPMCFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

LOADLIBES =  -L../isys -lisys -lpopt
CFLAGS = -Wall -g
LDFLAGS = -g 

ifneq ($(ARCH),ia64)
MODDEPS=moddeps
endif

all:	modlist $(MODDEPS) genhdlist snarffont mapshdr readmap

moddeps: moddeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o ../loader/modules.o \
            $(LOADLIBES) \
	    ../isys/modutils/insmod/libmodutils.a    \
	    ../isys/modutils/util/libutil.a          \
	    ../isys/modutils/obj/libobj.a -lrpm -lbz2 -lz -lpopt

genhdlist: genhdlist.c
	$(CC) -I/usr/include/rpm $(LDFLAGS) -o genhdlist genhdlist.c -lrpm -lbz2 -static -lz -lpopt -ldb

install: all
	mkdir -p $(DESTDIR)/usr/bin
#	install -m755 -s genhdlist $(DESTDIR)/usr/bin

#
# removed genhdlist from clean line so it will be distributed on CDROM image
#
clean:	
	rm -f modlist moddeps snarffont *.o 

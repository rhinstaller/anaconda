LOADLIBES =  -L../isys -lisys -lpopt
CFLAGS = -Wall -g
LDFLAGS = -g 

all:	modlist moddeps genhdlist snarffont

moddeps: moddeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o ../loader/modules.o \
            $(LOADLIBES) \
	    ../isys/modutils/insmod/libmodutils.a    \
	    ../isys/modutils/util/libutil.a          \
	    ../isys/modutils/obj/libobj.a -lrpm -lbz2 -lz -lpopt

genhdlist: genhdlist.c
	$(CC) -I/usr/include/rpm $(LDFLAGS) -o genhdlist genhdlist.c -lrpm -lbz2 -static -lz -lpopt

snarffont: snarffont.c
	$(CC) -o snarffont snarffont.c

install: all
	mkdir -p $(DESTDIR)/usr/bin
#	install -m755 -s genhdlist $(DESTDIR)/usr/bin

clean:	
	rm -f modlist genhdlist moddeps snarffont *.o 

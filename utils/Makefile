LOADLIBES = -lpopt -L../isys -lisys
CFLAGS = -Wall -g
LDFLAGS = -g

all:	modlist moddeps genhdlist snarffont

moddeps: moddeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o ../loader/modules.o \
            $(LOADLIBES) \
	    ../isys/modutils/insmod/libmodutils.a    \
	    ../isys/modutils/util/libutil.a          \
	    ../isys/modutils/obj/libobj.a -lrpm -lbz2 -lz

genhdlist: genhdlist.c
	$(CC) -I/usr/include/rpm $(LDFLAGS) -o genhdlist genhdlist.c -lrpm -lbz2

snarffont: snarffont.c
	$(CC) -o snarffont snarffont.c

install:
	@echo "nothing to do"		

clean:	
	rm -f modlist *.o

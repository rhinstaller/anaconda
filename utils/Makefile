LOADLIBES = -lpopt -L../isys -lisys
CFLAGS = -Wall -g
LDFLAGS = -g

all:	modlist moddeps

moddeps: moddeps.o
	$(CC) $(LDFLAGS) -o moddeps moddeps.o ../loader/modules.o \
            $(LOADLIBES) \
	    ../isys/modutils/insmod/libmodutils.a    \
	    ../isys/modutils/util/libutil.a          \
	    ../isys/modutils/obj/libobj.a -lrpm -lbz2 -lz
		

clean:	
	rm -f modlist

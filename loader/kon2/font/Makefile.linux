OBJ	= fld.o minix.o fontx2.o bdf.o j3100.o

ifeq (../.config,$(wildcard ../.config))
include ../.config
endif

#CC = cc -g
#LD = cc -g

LOADLIBES = $(LIB)

all:	fld

fld:	$(OBJ) $(LIB)
	$(LD) -o fld $(OBJ) $(LIB)

bdfcat: bdf.c $(LIB)
	$(CC) $(CFLAGS) -DBDFCAT -o bdfcat bdf.c $(LIB)

depend .depend:
	$(CC) $(CFLAGS) -M *.c > .depend

clean:
	$(RM) *.o fld fontx.c *~ .depend

install: fld
	$(INSTALL) -m 4755 fld $(BINDIR)

ifeq (.depend,$(wildcard .depend))
include .depend
endif

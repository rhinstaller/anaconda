OBJ	= sockface.o getcap.o mem.o font.o coding.o
LIB	= libgon.a

ifeq (../.config,$(wildcard ../.config))
include ../.config
endif

all:	$(LIB)

$(LIB):	$(OBJ)
	$(AR) rcs $(LIB) $(OBJ)

depend .depend:
	$(CC) $(CFLAGS) -M *.c > .depend

clean:
	$(RM) -f $(OBJ) $(LIB) *~ .depend

install: all

ifeq (.depend,$(wildcard .depend))
include .depend
endif

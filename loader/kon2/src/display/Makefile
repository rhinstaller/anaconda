OBJS	=
DISP	= ../display.a

ifeq (../../.config,$(wildcard ../../.config))
include ../../.config
endif

ifdef	HAS_S3
OBJS	:= $(OBJS) s3.o
endif
ifdef	HAS_J31SX
OBJS	:= $(OBJS) j31sx.o
endif
OBJS	:= $(OBJS) svga.o vga.o

#CC := $(CC) -g
#LD := $(CC) -g

all:	$(DISP)

$(DISP):	$(OBJS)
	$(AR) rcs $(DISP) $(OBJS)

depend .depend:
	$(CC) $(CFLAGS) -M *.c > .depend

clean:
	$(RM) -f *.o $(DISP) *~ .depend

install: all

ifeq (.depend,$(wildcard .depend))
include .depend
endif

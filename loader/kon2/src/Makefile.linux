DISP	= display.a
OBJS	= vt.o sock.o fnld.o vc.o mouse.o term.o main.o utmp.o errors.o child.o
KON	= kon

ifeq (../.config,$(wildcard ../.config))
include ../.config
endif

#CC := $(CC) -g
#LD := $(CC) -lgmon
SUBDIRS = display

all:	subdirs $(KON)

$(KON):	$(OBJS) $(DISP) $(LIB)
	$(LD) -o $(KON) $(OBJS) $(DISP) $(LIB)

depend .depend:
	$(CC) $(CFLAGS) -M *.c > .depend
	@for i in $(SUBDIRS);\
	do (cd $$i && echo building dependencies in $$i && $(MAKE) depend) || exit;\
	done

subdirs:
	@for i in $(SUBDIRS);\
	do (cd $$i && echo making all in $$i && $(MAKE)) || exit;\
	done

clean:
	$(RM) -f *.o $(KON) *~ .depend
	@for i in $(SUBDIRS);\
	do (cd $$i && echo cleaning all in $$i && $(MAKE) clean) || exit;\
	done

install: $(KON)
	$(INSTALL) -m 4755 $(KON) $(BINDIR)

ifeq (.depend,$(wildcard .depend))
include .depend
endif

TOOLS	= swkon rel newvc mkminifont
SRCS	= swkon.c rel.c newvc.c mkminifont.c

ifeq (../.config,$(wildcard ../.config))
include ../.config
endif

ifdef	SYSLOG_K
SYSTOOLS = syslogk
SYSSRCS	 = syslogk.c
SYSDIR	 = $(TOPDIR)/etc
endif
CC:=$(CC) -g

LDFLAGS = -N
LOADLIBES = $(LIB)

all:	$(TOOLS) $(SYSTOOLS)

depend .depend:
	$(CC) $(CFLAGS) -M $(SRCS) $(SYSSRCS) > .depend

clean:
	$(RM) -f *.o $(TOOLS) $(SYSTOOLS) *~ .depend

install: all
	$(INSTALL) swkon $(BINDIR)
	$(INSTALL) -m 4755 newvc $(BINDIR)
ifdef	SYSLOG_K
	$(INSTALL) $(SYSTOOLS) $(SYSDIR)
endif

swkon: $(LIB)

ifeq (.depend,$(wildcard .depend))
include .depend
endif

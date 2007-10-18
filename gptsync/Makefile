#
# Makefile for gptsync on Unix platforms
#


TARGETS	  = gptsync showpart
OBJS	  = showpart.c lib.c os_unix.c gptsync.c

CPPFLAGS = $(CFLAGS)
#CPPFLAGS = $(shell echo $(CFLAGS) | sed -e 's/-O2/-O0/g' -e 's/-g /-ggdb3 /g') 
CPPFLAGS += -D_LARGEFILE_SOURCE -D_FILE_OFFSET_BITS=64 
LDFLAGS   =
LIBS      =
CC	  = gcc

include ../Makefile.inc

# real making

all: $(TARGETS)

gptsync: gptsync.o lib.o
	$(CC) $(CPPFLAGS) $(LDFLAGS) -DPROGNAME=$@ -o $@ os_unix.c $^ $(LIBS)

showpart: showpart.o lib.o
	$(CC) $(CPPFLAGS) $(LDFLAGS) -DPROGNAME=$@ -o $@ os_unix.c $^ $(LIBS)

%.o: %.c
	$(CC) $(CPPFLAGS) -c -o $@ $<

# cleanup

clean:
	$(RM) *.o *~ *% $(TARGETS) .depend

# automatic dependencies

depend: dep
dep:
	for i in $(OBJS:.o=.c) ; do $(CC) $(CPPFLAGS) -MM $$i ; done > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif

# eof

# install target for anaconda
install: all
	mkdir -p $(DESTDIR)/usr/sbin
	install -m 755 gptsync $(DESTDIR)/usr/sbin/gptsync
	install -m 755 showpart $(DESTDIR)/usr/sbin/showpart

#
# Makefile for gptsync on Unix platforms
#

OBJS   = gptsync.o os_unix.o

TARGET = gptsync

CPPFLAGS = -D_LARGEFILE_SOURCE -D_FILE_OFFSET_BITS=64 
CFLAGS   = -Wall -Werror
LDFLAGS  =
LIBS     =

# real making

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $(TARGET) $(OBJS) $(LIBS)

$(OBJS): %.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $<

# cleanup

clean:
	$(RM) *.o *~ *% $(TARGET) .depend

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

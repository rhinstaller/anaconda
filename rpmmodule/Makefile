
# Makefile for the RPM bindigs for python
#
# $Id$

# Try to let other people continue using it
-include ../Makefile.inc

# If the above did not exist, then hardcode it here
ifndef PYTHONLIBDIR
PYTHONLIBDIR = /usr/lib/python1.5
endif
# end of ugly useability hack

PYTHON   = $(DESTDIR)/$(PYTHONLIBDIR)

CC       = gcc

INCLUDES = -I/usr/include/rpm -I/usr/include/python1.5
CFLAGS   = -Wall -fPIC -g -DHAVE_LIBIO $(INCLUDES)

LIBS     = -lrpm -lbz2 -lz -ldb1
LDFLAGS  = -g -shared -Wl,-soname,$(TARGET) $(LIBS)

# what are we building here?
TARGET   = rpmmodule.so

all: $(TARGET) 

rpmmodule.so: rpmmodule.o upgrade.o hash.o
	$(CC) -o $@ $^ $(LDFLAGS)

clean:
	rm -f *.o $(TARGET) *~

install: $(TARGET)
	[ -d $(PYTHON) ] || install -d $(PYTHON)
	install -m 755  $(TARGET) $(PYTHON)

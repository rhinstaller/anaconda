
# Makefile for the RPM bindigs for python
#
# $Id$

include ../Makefile.inc

PYTHON   = $(DESTDIR)/$(PYTHONLIBDIR)

CC       = gcc

INCLUDES = -I/usr/include/rpm -I/usr/include/python1.5
CFLAGS   = -Wall -fPIC -g -DHAVE_LIBIO $(INCLUDES)

LIBS     = -lrpm -lbz2 -lz -ldb1
LDFLAGS  = -shared -Wl,-soname,$(TARGET) $(LIBS)

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

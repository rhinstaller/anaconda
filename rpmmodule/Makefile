#
# Makefile for the RPM bindigs for python
#
# $Id$

PYTHON   = $(DESTDIR)/usr/lib/python1.5/site-packages

CC       = gcc

INCLUDES = -I/usr/include/rpm -I/usr/include/python1.5
CFLAGS   = -Wall -fPIC -g $(INCLUDES)

LIBS     = -lrpm -lz -ldb1
LDFLAGS  = -shared -Wl,-soname,$(TARGET) $(LIBS)

# what are we building here?
TARGET   = rpmmodule.so

all: $(TARGET) 

rpmmodule.so: rpmmodule.o upgrade.o hash.o
	$(CC) -o $@ $^ $(LDFLAGS)

clean:
	rm -f *.o $(TARGET) *~

install: $(TARGET)
	install -d $(PYTHON)
	install -m 755  $(TARGET) $(PYTHON)

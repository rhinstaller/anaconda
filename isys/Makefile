#
# Makefile
#
# Copyright (C) 2007, 2008 Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

include ../Makefile.inc

CFLAGS +=  -I$(PYTHONINCLUDE) -I.. -DHAVE_NFS

OBJECTS = devices.o imount.o smp.o cpio.o uncpio.o dasd.o \
          lang.o isofs.o linkdetect.o vio.o \
          ethtool.o eddsupport.o iface.o str.o auditd.o
SOBJECTS = $(patsubst %.o,%.lo,$(OBJECTS))
SOURCES = $(patsubst %.o,%.c,$(OBJECTS)) isys.c
LOADLIBES = -lresolv -lpopt -lext2fs -lz -ldevmapper -lblkid -lX11
LOADLIBES += $(SELINUXLIBES)
ifeq ($(USESELINUX),1)
LOADLIBES += -laudit
endif
PYMODULES = _isys.so
SUBDIRS = 

# D-Bus
LOADLIBES += $(shell pkg-config --libs dbus-1)
CFLAGS    += $(shell pkg-config --cflags dbus-1)

# NetworkManager
LOADLIBES += $(shell pkg-config --libs NetworkManager)
CFLAGS    += $(shell pkg-config --cflags NetworkManager)

# libnl
LOADLIBES += $(shell pkg-config --libs libnl-1)
CFLAGS    += $(shell pkg-config --cflags libnl-1)

ifeq ($(ARCH),ppc)
OBJECTS += minifind.o
SOURCES += minifind.c
endif

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: subdirs $(PYMODULES) libisys.a

%.lo: %.c
	$(CC) -c $(CFLAGS) -fPIC -o $@ $<

_isys.so: isys.lo $(SOBJECTS)
	gcc -shared -g -fPIC -o $@ isys.lo $(SOBJECTS) $(LOADLIBES) $(LDFLAGS)

libisys.a: libisys.a($(OBJECTS))

clean:
	rm -f *.o *.so *.lo *.a *.pyc $(TARGET) $(SOBJECTS)
	rm -f $(OBJECTS)
	rm -f .depend
	for d in $(SUBDIRS); do make -C $$d clean; done

install: all
	install -s $(PYMODULES) $(DESTDIR)/$(PYTHONLIBDIR)
	install isys.py $(DESTDIR)/$(PYTHONLIBDIR)

subdirs:
	for d in $(SUBDIRS); do make -C $$d; done

depend:
	$(CPP) -M $(CFLAGS) $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif

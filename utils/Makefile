#
# Makefile
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

ISYSLIB=isys

LOADERDIR = ../loader
LOADLIBES =  -lpopt
CFLAGS += -I.. -I$(LOADERDIR) -fno-strict-aliasing
RPMCFLAGS = $(CFLAGS) -I/usr/include/rpm

UTILS = modlist snarffont mapshdr readmap
ifeq (s390, $(ARCH))
UTILS += geninitrdsz mk-s390-cdboot
endif
ifeq (s390x, $(ARCH))
UTILS += geninitrdsz mk-s390-cdboot
endif

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: $(UTILS)

modlist: modlist.o moduleinfo.o
	$(CC) $(LDFLAGS) -o modlist modlist.o moduleinfo.o $(LOADLIBES)

moduleinfo.o: $(LOADERDIR)/moduleinfo.c
	cp $(LOADERDIR)/moduleinfo.c ./
	$(CC) $(CFLAGS) -c moduleinfo.c

moduledeps.o: $(LOADERDIR)/moduledeps.c
	cp $(LOADERDIR)/moduledeps.c ./
	$(CC) $(CFLAGS) -c moduledeps.c

md5.o: md5.c md5.h
	gcc -c -O -g md5.c -D_FORTIFY_SOURCE=2

hash.o : hash.c
	$(CC) $(RPMCFLAGS) -c -o $@ $<

geninitrdsz: geninitrdsz.c
	$(CC) $(CFLAGS) -o $@ $<

mk-s390-cdboot: mk-s390-cdboot.c
	$(CC) $(CFLAGS) -o $@ $<

depends:

install: all
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 genmodinfo $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 trimpciids $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 modlist $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 readmap $(DESTDIR)/$(RUNTIMEDIR)
	install -m755 mapshdr $(DESTDIR)/$(RUNTIMEDIR)
	if [ -x geninitrdsz ]; then \
		install -m755 geninitrdsz $(DESTDIR)/$(RUNTIMEDIR) ; \
	fi
	if [ -x mk-s390-cdboot ]; then \
		install -m755 mk-s390-cdboot $(DESTDIR)/$(RUNTIMEDIR) ; \
	fi

clean:	
	rm -f modlist snarffont mapshdr readmap geninitrdsz \
	moduledeps.c moduleinfo.c .depend *.o

depend:
	$(CPP) -M $(RPMCFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

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

LIBUTF8 = libunicode-lite.so.1

OBJECTS = unicode-lite.o

TARGETS= $(LIBUTF8)

all:	$(TARGETS) libunicode-lite.a

CFLAGS += -I../wlite/

$(LIBUTF8): unicode-lite.c
	gcc -fPIC -shared -I../wlite/ -o $@ $< -D_FORTIFY_SOURCE=2 ../wlite/libwlite.a $(LDFLAGS)

libunicode-lite.a: libunicode-lite.a($(OBJECTS))

clean:
	rm -f *.so.* *.o *.a

install:
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)
	for lib in $(TARGETS) ; do install $$lib $(DESTDIR)/$(RUNTIMEDIR) ; done

depend:

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
VERSION := $(shell awk '/Version:/ { print $$2 }' ../anaconda.spec)

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

LIBS = -lnewt -lslang -lz -lpopt ../isys/libisys.a -lcheckisomd5

# devmapper
LIBS   += $(shell pkg-config --libs devmapper)
CFLAGS += $(shell pkg-config --cflags devmapper)

# libnl
LIBS   += $(shell pkg-config --libs libnl-1)
CFLAGS += $(shell pkg-config --cflags libnl-1)

# NetworkManager
CFLAGS += $(shell pkg-config --cflags NetworkManager)

# D-Bus
LIBS   += $(shell pkg-config --libs dbus-1)
CFLAGS += $(shell pkg-config --cflags dbus-1)

ifeq (1, $(USESELINUX))
LIBS += -lselinux -lsepol
endif

# These libs need to be on the end of the link list
LIBS += -lresolv -lm

BINS = loader

HWOBJS = hardware.o
METHOBJS = method.o cdinstall.o hdinstall.o nfsinstall.o urlinstall.o 
OBJS = copy.o log.o moduleinfo.o loadermisc.o modules.o windows.o \
	lang.o kbd.o driverdisk.o selinux.o \
	mediacheck.o kickstart.o driverselect.o \
	getparts.o dirbrowser.o fwloader.o \
	$(HWOBJS) $(METHOBJS)
LOADEROBJS = loader.o loader-pcmcia.o
NETOBJS = net.o urls.o ftp.o telnet.o telnetd.o
SOURCES = $(subst .o,.c,$(OBJS)) loader.c

LIBS +=

CFLAGS += -DUSE_LOGDEV -DVERSION='"$(VERSION)"' -D_GNU_SOURCE
REALCC=gcc

# linuxrc + shutdown on s390, init everywhere else
ifneq (,$(filter s390 s390x,$(ARCH)))
BINS += linuxrc.s390 shutdown
SHUTDOWNOPTS = -DAS_SHUTDOWN=1
else
BINS += init
endif

# translation stuff
LANGS = $(shell cut -f 2 ../lang-table | egrep -v '(^en$$)')

TR = $(patsubst %,tr/%.tr,$(LANGS))
TRFILES = $(patsubst %,%.tr,$(LANGS))

all: $(BINS) loader.tr

loader.tr: $(TR) ../lang-table
	(cd tr; ls $(TRFILES) | cpio --quiet -Hcrc -o |gzip -9) > $@

tr/%.tr: ../po/%.po loader.po
	msgmerge -q $< loader.po | msgconv -t utf-8 | ./simplemot > $@

loader.po: $(wildcard *.c)
	xgettext --default-domain=loader --add-comments \
		--keyword=_ --keyword=N_ *.c
	sed -i 's/charset=CHARSET/charset=UTF-8/' $@

linuxrc.s390:
	@echo "Nothing to do for $@"

init: init.o undomounts.o shutdown.o copy.o
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

shutdown: shutdown.o undomounts.o
	$(CC) $(CFLAGS) $(SHUTDOWNOPTS) $(LDFLAGS) -o $@ $^

init.o: init.c devices.h
	$(CC) $(CFLAGS) -c -o init.o init.c

undomounts.o: undomounts.c
	$(CC) $(CFLAGS) -c -o undomounts.o undomounts.c

shutdown.o: shutdown.c
	$(CC) $(CFLAGS) $(SHUTDOWNOPTS) -c -o shutdown.o shutdown.c

mkctype: mkctype.c
	$(REALCC) $(CFLAGS) -o mkctype mkctype.c

ctype.c: mkctype
	./mkctype > ctype.c

loader.o: loader.c
	$(CC) -DINCLUDE_LOCAL -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader-local.o: loader.c
	$(CC) -DINCLUDE_LOCAL $(CFLAGS) -o $@ -c $<

loader-net.o: loader.c
	$(CC) -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader: loader.o $(OBJS) $(NETOBJS)
	$(CC) -g -o $@ $^ $(LIBS) $(LDFLAGS)

clean:
	rm -f *.o *~ .depend init ctype.c mkctype loader
	rm -rf tr/*

depend: $(CTYPEDEP)
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

install: all
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)/loader
	for n in $(BINS); do \
	    install -m 755 $$n $(DESTDIR)/$(RUNTIMEDIR)/loader; \
	done
	if [ -f keymaps-$(ARCH) ]; then cp keymaps-$(ARCH) $(DESTDIR)/$(RUNTIMEDIR)/keymaps-override-$(ARCH) ; fi
	install -m 644 unicode-linedraw-chars.txt $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 loader.tr $(DESTDIR)/$(RUNTIMEDIR)/loader

dirbrowser: dirbrowser.c
	gcc -DSTANDALONE -D_FORTIFY_SOURCE=2 -Wall -Werror -ggdb -o dirbrowser dirbrowser.c -lnewt -lslang

ifeq (.depend,$(wildcard .depend))
include .depend
endif

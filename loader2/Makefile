include ../Makefile.inc
VERSION := $(shell awk '/Version:/ { print $$2 }' ../anaconda.spec)

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

SLANGLIB = -lslang
NEWTLIB = -lnewt
BTERMLIB = -lbterm -lbogl 
WLITELIB = -lwlite
ISYSLIB = ../isys/libisys.a
GUNZIP = -lz

BINS = loader

HWOBJS = pcmcia.o usb.o firewire.o hardware.o
METHOBJS = method.o cdinstall.o hdinstall.o nfsinstall.o urlinstall.o 
OBJS = log.o moduleinfo.o loadermisc.o modules.o moduledeps.o windows.o \
	lang.o kbd.o modstubs.o driverdisk.o selinux.o \
	md5.o mediacheck.o kickstart.o driverselect.o \
	getparts.o dirbrowser.o \
	$(HWOBJS) $(METHOBJS)
LOADEROBJS = loader.o loader-pcmcia.o
NETOBJS = net.o urls.o ftp.o telnet.o telnetd.o
PCMCIAOBJS = pcmcia.o $(NETOBJS)
SOURCES = $(subst .o,.c,$(OBJS)) loader.c

HWLIBS = -lkudzu_loader  
ifeq (1, $(USEDIET))
HWLIBS += -lpci_loader
else
HWLIBS += -lpci
endif

DEBUG = -ggdb
COPTS = $(DEBUG) -Os -Wall -DUSE_LOGDEV -DVERSION='"$(VERSION)"' -Werror
CFLAGS = $(COPTS) -ffunction-sections -D_GNU_SOURCE=1 -D_FILE_OFFSET_BITS=64 -DHAVE_LIBIO_H 
STATIC = -static
REALCC=gcc

ifeq (1, $(USEDIET))
CFLAGS += -DGZLIB=1 -DDIET=1
DIET=diet
CC=$(DIET) $(REALCC)
BTERMLIB = -lbtermdiet -lbogldiet 
WLITELIB = -lwlitediet
ISYSLIB = ../isys/libisys-diet.a
GUNZIP = ../isys/gzlib/libgunzip-diet.a

OBJS += dietstubs.o ctype.o
ISYSLIB += -lrpc
CTYPEDEP = ctype.c
else
OBJS += wcstubs.o
endif

# linuxrc + shutdown on s390, init everywhere else
ifneq (,$(filter s390 s390x,$(ARCH)))
BINS += linuxrc.s390 shutdown
SHUTDOWNOPTS = -DAS_SHUTDOWN=1
else
BINS += init
endif

# translation stuff
LANGS = $(shell awk '{ print $$2 }' ../lang-table | egrep -v '(^en$$)')

TR = $(patsubst %,tr/%.tr,$(LANGS))
TRFILES = $(patsubst %,%.tr,$(LANGS))

all: $(BINS) loader.tr font.bgf.gz

font.bgf.gz: /usr/lib/bogl/font.bdf.gz /usr/bin/reduce-font unicode-linedraw-chars.txt
	zcat /usr/lib/bogl/font.bdf.gz > font.bdf
	export LANG=en_US.UTF-8; (cat unicode-linedraw-chars.txt; for I in ../po/*.po ../po/timeconfig/*.po ; do msgconv -t utf-8 $$I; done) | reduce-font font.bdf > font-reduced.bdf
	bdftobogl -b font-reduced.bdf > font.bgf
	rm -f font.bdf font-reduced.bdf
	gzip -9 -f font.bgf

loader.tr: $(TR) ../lang-table
	(cd tr; ls $(TRFILES) | cpio --quiet -Hcrc -o |gzip -9) > $@

tr/%.tr: ../po/%.po loader.po
	msgmerge $< loader.po | msgconv -t utf-8 | ./simplemot > $@

loader.po: $(wildcard *.c)
	xgettext --default-domain=loader --add-comments \
		--keyword=_ --keyword=N_ *.c

linuxrc.s390:
	@echo "Nothing to do for $@"

init: init.o undomounts.o shutdown.o
	$(REALCC) $(STATIC) $(COPTS) $(LDFLAGS) -o $@ $^ ../isys/libisys.a -lresolv

shutdown: shutdown.o undomounts.o
	$(CC) $(STATIC) $(COPTS) $(SHUTDOWNOPTS) $(LDFLAGS) -o $@ $^ ../isys/libisys.a -lresolv

init.o: init.c
	$(CC) $(COPTS) -c -o init.o init.c

undomounts.o: undomounts.c
	$(REALCC) $(COPTS) -c -o undomounts.o undomounts.c

shutdown.o: shutdown.c
	$(CC) $(COPTS) $(SHUTDOWNOPTS) -c -o shutdown.o shutdown.c

mkctype: mkctype.c
	$(REALCC) $(COPTS) -o mkctype mkctype.c

ctype.c: mkctype
	./mkctype > ctype.c

loader.o: loader.c
	$(CC) -DINCLUDE_LOCAL -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader-local.o: loader.c
	$(CC) -DINCLUDE_LOCAL $(CFLAGS) -o $@ -c $<

loader-net.o: loader.c
	$(CC) -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader: loader.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	$(HWLIBS) $(ISYSLIB) $(GUNZIP) \
	-lpump -lresolv $(NEWTLIB) $(SLANGLIB) $(BTERMLIB) $(WLITELIB)

clean:
	rm -f *.o *~ .depend init ctype.c mkctype \
	loader

depend: $(CTYPEDEP)
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

install: all
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)/loader
	for n in $(BINS); do \
	    install -m 755 $$n $(DESTDIR)/$(RUNTIMEDIR)/loader; \
	    strip $(DESTDIR)/$(RUNTIMEDIR)/loader/$$n || :; \
	done
	install -m 644 loader.tr $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 module-info $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 font.bgf.gz $(DESTDIR)/$(RUNTIMEDIR)/loader

dirbrowser: dirbrowser.c
	gcc -DSTANDALONE -Wall -Werror -ggdb -o dirbrowser dirbrowser.c -lnewt -lslang

ifeq (.depend,$(wildcard .depend))
include .depend
endif

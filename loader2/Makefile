include ../Makefile.inc
VERSION := $(shell awk '/Version:/ { print $$2 }' ../anaconda.spec)

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

# glib - for utility stuff
GLIB   = $(shell pkg-config --libs glib-2.0)
CFLAGS += $(shell pkg-config --cflags glib-2.0)

# dhcp library flags
DHCP   = $(shell pkg-config --libs libdhcp)
CFLAGS += $(shell pkg-config --cflags libdhcp)

SLANGLIB = -lslang
NEWTLIB = -lnewt
ISYSLIB = ../isys/libisys.a
GUNZIP = -lz
DMLIB = -ldevmapper
ifeq (1, $(USESELINUX))
DMLIB += -lselinux -lsepol
endif

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

CFLAGS += -DUSE_LOGDEV -DVERSION='"$(VERSION)"'
STATIC = -static
REALCC=gcc

ifeq (1, $(USEDIET))
CFLAGS += -DGZLIB=1 -DDIET=1
DIET=diet
CC=$(DIET) $(REALCC)
ISYSLIB = ../isys/libisys-diet.a
GUNZIP = ../isys/gzlib/libgunzip-diet.a

OBJS += dietstubs.o ctype.o
ISYSLIB += -lrpc
CTYPEDEP = ctype.c
else
UNICODELIB = ../stubs/libunicode-lite.a
endif

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

init: init.o undomounts.o shutdown.o
	$(CC) $(STATIC) $(CFLAGS) $(LDFLAGS) -o $@ $^

shutdown: shutdown.o undomounts.o
	$(CC) $(STATIC) $(CFLAGS) $(SHUTDOWNOPTS) $(LDFLAGS) -o $@ $^

init.o: init.c
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
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	$(HWLIBS) $(ISYSLIB) $(GUNZIP) $(UNICODELIB) \
	-lresolv $(NEWTLIB) $(SLANGLIB) $(DMLIB) $(GLIB) $(DHCP) -lm

clean:
	rm -f *.o *~ .depend init ctype.c mkctype \
	loader checkisomd5

depend: $(CTYPEDEP)
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

checkisomd5: depend mediacheck.c log.c md5.c
	$(CC) -DTESTING $(CFLAGS) -o mediacheck.o -c mediacheck.c
	$(CC) -DTESTING $(CFLAGS) -o log.o -c log.c
	$(CC) -DTESTING $(CFLAGS) -o md5.o -c md5.c
	$(CC) -g $(STATIC) -o checkisomd5 mediacheck.o log.o md5.o \
		$(NEWTLIB) $(SLANGLIB)

install: all
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)/loader
	for n in $(BINS); do \
	    install -m 755 $$n $(DESTDIR)/$(RUNTIMEDIR)/loader; \
	done
	if [ -f keymaps-$(ARCH) ]; then cp keymaps-$(ARCH) $(DESTDIR)/$(RUNTIMEDIR)/keymaps-override-$(ARCH) ; fi
	install -m 644 unicode-linedraw-chars.txt $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 loader.tr $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 module-info $(DESTDIR)/$(RUNTIMEDIR)/loader

dirbrowser: dirbrowser.c
	gcc -DSTANDALONE -D_FORTIFY_SOURCE=2 -Wall -Werror -ggdb -o dirbrowser dirbrowser.c -lnewt -lslang

ifeq (.depend,$(wildcard .depend))
include .depend
endif

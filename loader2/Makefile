include ../Makefile.inc

# JKFIXME: this should go somewhere common.  I need to know about diet in
# a few locations.  and we should really just always use diet
# should we use diet on this arch?
ifeq (i386, $(ARCH))
USEDIET=1
endif
ifeq (ppc, $(ARCH))
USEDIET=1
endif

# JKFIXME: switch to use system libslang and libnewt with msw's wcwidth()
SLANGLIB = ../minislang/libslang.a
NEWTLIB = ../mininewt/libnewt.a
ISYSLIB = ../isys/libisys.a
GUNZIP = -lz
MODULELINKAGE :=-lmodutils -lmodutilutil -lmodutilobj

BINS = init

HWOBJS = pcmcia.o usb.o firewire.o
METHOBJS = method.o cdinstall.o nfsinstall.o urlinstall.o
OBJS = log.o moduleinfo.o loadermisc.o modules.o moduledeps.o windows.o \
	lang.o kbd.o modules.o modstubs.o \
	md5.o mediacheck.o \
	$(HWOBJS) $(METHOBJS)
LOADEROBJS = loader.o loader-pcmcia.o
NETOBJS = net.o urls.o telnet.o telnetd.o
NETOBJS = net.o urls.o ftp.o
PCMCIAOBJS = pcmcia.o $(NETOBJS)
SOURCES = $(subst .o,.c,$(OBJS)) loader.c

HWLIBS = -lkudzu_loader  -lpci

DEBUG = -ggdb
COPTS = $(DEBUG) -Wall -DVERSION='"$(VERSION)"'
CFLAGS = $(COPTS) -Os -ffunction-sections -D_GNU_SOURCE=1 -D_FILE_OFFSET_BITS=64 -DHAVE_LIBIO_H -DPRODUCTNAME='$(PRODUCTNAME)'
STATIC = -static


ifeq (1, $(USEDIET))
CFLAGS += -DGZLIB=1
DIET=diet
REALCC=gcc
CC=$(DIET) $(REALCC)
# JKFIXME: this also goes away when we go to system {newt,slang}
SLANGLIB = ../minislang/libslang-diet.a
NEWTLIB = ../mininewt/libnewt-diet.a
ISYSLIB = ../isys/libisys-diet.a
GUNZIP = ../isys/gzlib/libgunzip-diet.a
endif

ifeq (i386, $(ARCH))
BINS += loader
OBJS += dietstubs.o ctype.o
COPTS += -DUSE_LOGDEV
ISYSLIB += -lrpc
endif

all: $(BINS)

init: init.o
	$(CC) $(STATIC) $(COPTS) $(LDFLAGS) -o $@ init.o

init.o: init.c
	$(CC) $(COPTS) -c -o init.o init.c

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

loader-pcmcia.o: loader.c
	$(CC) -DINCLUDE_PCMCIA -DINCLUDE_LOCAL -DINCLUDE_NETWORK \
	    $(CFLAGS) -o $@ -c $<

loader: loader.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	$(HWLIBS) $(ISYSLIB) \
	$(MODULELINKAGE) $(GUNZIP) \
	-lpump $(NEWTLIB) $(SLANGLIB)  $(KONOBJS)

loader-local: loader-local.o $(OBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	$(HWLIBS) $(ISYSLIB) \
	$(MODULELINKAGE) $(GUNZIP) \
        -L ../stubs $(NEWTLIB) $(SLANGLIB)  $(KONOBJS)

loader-network: loader-net.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	$(HWLIBS) $(ISYSLIB) \
	$(MODULELINKAGE) $(GUNZIP) \
        -lpump -L ../stubs $(NEWTLIB) $(SLANGLIB)  $(KONOBJS)

loader-pcmcia: loader-pcmcia.o pcmcia.o popen.o $(OBJS) $(PCMCIAOBJS)
	$(CC) -g $(STATIC) -o $@ loader-pcmcia.o $(OBJS) \
	    $(PCMCIAOBJS) -lcardmgr_loader -lprobe_loader popen.o \
        -lpopt     \
        $(HWLIBS) $(ISYSLIB) \
	$(MODULELINKAGE) $(GUNZIP) \
        -lpump -lresolv $(NEWTLIB) $(SLANGLIB)  $(KONOBJS)



clean:
	rm -f *.o *~ .depend init ctype.c mkctype \
	loader loader-pcmcia loader-local loader-network

depend:
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

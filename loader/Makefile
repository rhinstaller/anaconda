include ../Makefile.inc

VERSION = 7.2

DESTDIR = ../../trees/initrd

OBJS = log.o windows.o modules.o devices.o cdrom.o urls.o kickstart.o lang.o \
       misc.o ftp.o md5.o mediacheck.o

SLANGLIB = -lslang
ifneq (ia64, $(ARCH))
ifneq (i386, $(ARCH))
OBJS += fnmatch-stub.o printf-stub.o pwd-stub.o dl-stub.o
SLANGLIB = ../minislang/libslang.a
endif
endif

LOADEROBJS = loader.o loader-pcmcia.o popen.o
SOURCES = $(subst .o,.c,$(OBJS)) loader.c
BINS = init
DIRS = 
NETOBJS = net.o telnet.o telnetd.o
PCMCIAOBJS = pcmcia.o $(NETOBJS)
OPTS = -Os
DEBUG = -g

MODULELINKAGE :=-lmodutils -lmodutilutil -lmodutilobj

COPTS = $(DEBUG) -Wall -DVERSION='"$(VERSION)"' 

CFLAGS = $(COPTS) $(OPTS) -ffunction-sections -D_GNU_SOURCE=1 -I/usr/include/kudzu -I/usr/include/rpm -I.. -DHAVE_LIBIO_H -ggdb

ALLOBJS = $(OBJS) $(PCMCIAOBJS)

ISYS = ../isys/libisys.a
GUNZIP = ../isys/gzlib/libgunzip.a
LOADERLIBS = -lpci

# XXX Japanese is i386 only at the moment
ifeq (i386, $(ARCH))
BINS += loader-local loader-network loader-pcmcia
 ifeq (1, $(JAPANESE))
 KONOBJS = ./kon2/src/libkon.a ./kon2/src/display.a ./kon2/lib/libgon.a
 CFLAGS += -DINCLUDE_KON
 DIRS += kon2
 endif
OBJS += dietstubs.o ctype.o
endif

ifeq (ia64, $(ARCH))
BINS += loader
endif

ifeq (alpha, $(ARCH))
BINS += loader
OBJS += stubs.o
endif

ifeq (s390, $(ARCH))
BINS += loader
OBJS += stubs.o
S390FILES = load_anaconda
endif

ifeq (s390x, $(ARCH))
BINS += loader
OBJS += stubs.o
S390FILES = load_anaconda
endif

ifeq (sparc, $(ARCH))
BINS += loader loader-local
OBJS += stubs.o
endif

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

STATIC = -static

ifeq (i386, $(ARCH))
MINILIBC=minilibc.o
COPTS+=-DUSE_MINILIBC=1 -DUSE_LOGDEV
LDFLAGS = -nostdlib /usr/lib/crt1.o
LOADERLIBS += -lrpc
ISYS = ../isys/libisys-diet.a
SLANGLIB = ../minislang/libslang-diet.a
GUNZIP = ../isys/gzlib/libgunzip-diet.a
DIET=diet
REALCC=gcc
CC=$(DIET) $(REALCC)
STATIC=-static
else
ifeq (sparc, $(ARCH))
MINILIBC=minilibc.o /usr/lib/libc.a
CFLAGS+=-DUSE_MINILIBC=1 -DUSE_LOGDEV
LDFLAGS = -nostdlib /usr/lib/crt1.o
STATIC=-static
else
CFLAGS+=-DUSE_MINILIBC=0
STATIC=-static
endif
endif

LANGS = $(shell awk '{ print $$2 }' ../lang-table | egrep -v '(^en$$)')

TR = $(patsubst %,tr/%.tr,$(LANGS))
TRFILES = $(patsubst %,%.tr,$(LANGS))

all: dirs $(BINS) loader.tr 

loader.tr: $(TR) ../lang-table
	(cd tr; ls $(TRFILES) | cpio --quiet -Hcrc -o | gzip -9) > $@

loader.po: *.c
	xgettext --default-domain=loader --add-comments \
		--keyword=_ --keyword=N_ *.c

#tr/%.tr: ../po/%.po loader.po
#	msgmerge $< loader.po | ./simplemot > $@

dirs:
	for n in . $(DIRS); do \
	    [ "$$n" = "." ] || make -C $$n ;\
	done

install: all
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)/loader
	for n in $(BINS); do \
	    install -m 755 $$n $(DESTDIR)/$(RUNTIMEDIR)/loader; \
	    strip $(DESTDIR)/$(RUNTIMEDIR)/loader/$$n; \
	done
	install -m 644 loader.tr $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 module-info $(DESTDIR)/$(RUNTIMEDIR)/loader
	for n in $(S390FILES); do \
	   install -m 755 s390/$$n $(DESTDIR)/$(RUNTIMEDIR)/loader; \
	done
	install -m 644 kon.cfg $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 minikon.fnt $(DESTDIR)/$(RUNTIMEDIR)/loader

urltest: urltest.o ftp.o urls.o lang.o log.o windows.o
	$(CC) -g -o urltest urltest.o -lnewt ftp.o urls.o lang.o log.o windows.o -lz $(ISYS) -lresolv

loader: loader.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	-lkudzu_loader $(ISYS) ../balkan/libbalkan.a \
	$(MODULELINKAGE) $(GUNZIP) \
	-lpump -lz -lnewt $(SLANGLIB) $(LOADERLIBS) $(KONOBJS)

loader-local: loader-local.o $(OBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	-lkudzu_loader $(ISYS) ../balkan/libbalkan.a \
	$(MODULELINKAGE) $(GUNZIP) \
        -L ../stubs -lz -lnewt $(SLANGLIB) $(LOADERLIBS) $(KONOBJS)

loader-network: loader-net.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	-lkudzu_loader $(ISYS) ../balkan/libbalkan.a \
	$(MODULELINKAGE) $(GUNZIP) \
        -lpump -L ../stubs -lnewt $(SLANGLIB) $(LOADERLIBS) $(KONOBJS)

loader-pcmcia: loader-pcmcia.o pcmcia.o popen.o $(OBJS) $(PCMCIAOBJS)
	$(CC) -g $(STATIC) -o $@ loader-pcmcia.o $(OBJS) \
	    $(PCMCIAOBJS) -lcardmgr_loader -lprobe_loader popen.o \
        -lpopt     \
        -lkudzu_loader $(ISYS) ../balkan/libbalkan.a \
	$(MODULELINKAGE) $(GUNZIP) \
        -lpump -lz -lresolv -lnewt $(SLANGLIB) $(LOADERLIBS) $(KONOBJS)

loader.o: loader.c
	$(CC) -DINCLUDE_LOCAL -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader-local.o: loader.c
	$(CC) -DINCLUDE_LOCAL $(CFLAGS) -o $@ -c $<

loader-net.o: loader.c
	$(CC) -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader-pcmcia.o: loader.c
	$(CC) -DINCLUDE_PCMCIA -DINCLUDE_LOCAL -DINCLUDE_NETWORK \
	    $(CFLAGS) -o $@ -c $<

init: init.o $(MINILIBC)
	$(REALCC) $(STATIC) $(COPTS) $(LDFLAGS) -o $@ init.o $(MINILIBC)

init.o: init.c 
	$(REALCC) -O2 $(COPTS) -c -o init.o init.c

minilibc.o: minilibc.c
	$(REALCC) -O2 $(COPTS) -c -o minilibc.o minilibc.c

mkctype: mkctype.c
	$(REALCC) $(COPTS) -o mkctype mkctype.c

ctype.c: mkctype
	./mkctype > ctype.c

clean: 
	rm -f *.o .depend *~ loader-local loader-network loader.old \
	      loader-pcmcia probe modprobe loader.po loader.tr tr/*.tr \
	      loader init ctype.c mkctype
	for n in $(DIRS); do \
	    (cd $$n; make clean) \
	done

depend:
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

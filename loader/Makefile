include ../Makefile.inc

VERSION = 7.0

DESTDIR = ../../trees/initrd

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

OBJS = log.o windows.o modules.o devices.o cdrom.o urls.o kickstart.o lang.o \
       misc.o ftp.o kudzustubs.o
ifneq (ia64, $(ARCH))
OBJS += fnmatch-stub.o printf-stub.o pwd-stub.o dl-stub.o
SLANGLIB = ../minislang/libslang.a
else
SLANGLIB = -lslang
endif

LOADEROBJS = loader.o loader-pcmcia.o popen.o
SOURCES = $(subst .o,.c,$(OBJS)) loader.c
BINS = init
DIRS = 
NETOBJS = net.o 
PCMCIAOBJS = pcmcia.o $(NETOBJS)
#OPTS = -O2 -g
OPTS = -O -g

MODULELINKAGE :=../isys/modutils/insmod/libmodutils.a    \
	       	../isys/modutils/util/libutil.a          \
	       	../isys/modutils/obj/libobj.a

CFLAGS = $(DEBUG) $(OPTS) -Wall -D_GNU_SOURCE=1 -I/usr/include/kudzu -I/usr/include/rpm -I.. -DUSE_ALT_DNS=1 -DVERSION='"$(VERSION)"' -DHAVE_LIBIO_H -ggdb

ALLOBJS = $(OBJS) $(PCMCIAOBJS)

# XXX Japanese is i386 only at the moment
ifeq (i386, $(ARCH))
BINS += loader-local loader-network loader-pcmcia
 ifeq (1, $(JAPANESE))
 BINS += loader-local-kon loader-network-kon loader-pcmcia-kon
 KONOBJS = ./kon2/src/libkon.a ./kon2/src/display.a ./kon2/lib/libgon.a
 endif
DIRS += pcmcia-install kon2
OBJS += stubs.o
endif

ifeq (ia64, $(ARCH))
BINS += loader
endif

ifeq (alpha, $(ARCH))
BINS += loader
OBJS += stubs.o
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
CFLAGS+=-DUSE_MINILIBC=1 -DUSE_LOGDEV
LDFLAGS = -nostdlib /usr/lib/crt1.o
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

LANGS = $(shell awk '{ print $$2 }' ../lang-table | egrep -v '(^en$$)|(^ja$$)')

TR = $(patsubst %,tr/%.tr,$(LANGS))
TRFILES = $(patsubst %,%.tr,$(LANGS))

all: dirs $(BINS) loader.tr kon-loader.tr

loader.tr: $(TR) ../lang-table
	(cd tr; ls $(TRFILES) | cpio --quiet -Hcrc -o | gzip -9) > $@

kon-loader.tr: tr/ja.tr ../lang-table
	(cd tr; echo ja.tr | cpio --quiet -Hcrc -o | gzip -9) > $@

loader.po: *.c
	xgettext --default-domain=loader --add-comments \
		--keyword=_ --keyword=N_ *.c

tr/%.tr: ../po/%.po loader.po
	msgmerge $< loader.po | ./simplemot > $@

dirs:
	for n in . $(DIRS); do \
	    [ "$$n" = "." ] || make -C $$n ;\
	done

install: all
	mkdir -p $(DESTDIR)/$(RUNTIMEDIR)/loader
	for n in $(BINS); do \
	    install -s -m 755 $$n $(DESTDIR)/$(RUNTIMEDIR)/loader; \
	done
	install -m 644 loader.tr $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 kon-loader.tr $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 module-info $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 kon.cfg $(DESTDIR)/$(RUNTIMEDIR)/loader
	install -m 644 minikon.fnt $(DESTDIR)/$(RUNTIMEDIR)/loader

urltest: urltest.o ftp.o urls.o lang.o log.o windows.o
	$(CC) -g -o urltest urltest.o -lnewt ftp.o urls.o lang.o log.o windows.o -lz ../isys/libisys.a -lresolv

loader: loader.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	-lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
	-lpump -lbz2 -lz -lresolv -lnewt $(SLANGLIB) -lpci

loader-local: loader-local.o $(OBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        -lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
        -L ../stubs -lz -lresolv -lnewt $(SLANGLIB) -lpci

loader-local-kon: loader-local-kon.o $(OBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        -lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
        -L ../stubs -lz -lresolv -lnewt $(SLANGLIB) -lpci \
	$(KONOBJS)

loader-network: loader-net.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        -lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
        -lpump -lbz2 -lz -lresolv -lnewt $(SLANGLIB) -lpci

loader-network-kon: loader-net-kon.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        -lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
        -lpump -lbz2 -lz -lresolv -lnewt $(SLANGLIB) -lpci \
	$(KONOBJS)

loader-pcmcia: loader-pcmcia.o pcmcia.o popen.o $(OBJS) $(PCMCIAOBJS)
	$(CC) -g $(STATIC) -o $@ loader-pcmcia.o $(OBJS) \
	    $(PCMCIAOBJS) -L pcmcia-install/cardmgr -lcardmgr -lprobe popen.o \
        -lpopt     \
        -lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
        -lpump -lbz2 -lz -lresolv -lnewt $(SLANGLIB) -lpci

loader-pcmcia-kon: loader-pcmcia-kon.o pcmcia.o popen.o $(OBJS) $(PCMCIAOBJS)
	$(CC) -g $(STATIC) -o $@ loader-pcmcia-kon.o $(OBJS) \
	    $(PCMCIAOBJS) -L pcmcia-install/cardmgr -lcardmgr -lprobe popen.o \
        -lpopt     \
        -lkudzu_loader ../isys/libisys.a ../balkan/libbalkan.a \
	$(MODULELINKAGE) \
        -lpump -lbz2 -lz -lresolv -lnewt $(SLANGLIB) -lpci \
        $(KONOBJS)

loader.o: loader.c
	$(CC) -DINCLUDE_LOCAL -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader-local.o: loader.c
	$(CC) -DINCLUDE_LOCAL $(CFLAGS) -o $@ -c $<

loader-local-kon.o: loader.c
	$(CC) -DINCLUDE_LOCAL -DINCLUDE_KON $(CFLAGS) -o $@ -c $<

loader-net.o: loader.c
	$(CC) -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $<

loader-net-kon.o: loader.c
	$(CC) -DINCLUDE_NETWORK -DINCLUDE_KON $(CFLAGS) -o $@ -c $<

loader-pcmcia.o: loader.c
	$(CC) -DINCLUDE_PCMCIA -DINCLUDE_LOCAL -DINCLUDE_NETWORK \
	    $(CFLAGS) -o $@ -c $<

loader-pcmcia-kon.o: loader.c
	$(CC) -DINCLUDE_PCMCIA -DINCLUDE_LOCAL -DINCLUDE_NETWORK \
	    -DINCLUDE_KON $(CFLAGS) -o $@ -c $<

init: init.o $(MINILIBC)
	$(CC) $(STATIC) -g $(LDFLAGS) -o $@ init.o $(MINILIBC)

clean: 
	rm -f *.o .depend *~ loader-local loader-network loader.old loader-pcmcia probe modprobe \
	      loader.po loader.tr tr/*.tr loader init loader-local-kon loader-network-kon \
              loader-pcmcia-kon
	for n in $(DIRS); do \
	    (cd $$n; make clean) \
	done

depend:
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

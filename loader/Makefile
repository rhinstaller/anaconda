VERSION = 6.2

DESTDIR = ../../trees/initrd

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

OBJS = log.o windows.o modules.o devices.o cdrom.o urls.o kickstart.o lang.o \
       misc.o ftp.o
LOADEROBJS = loader.o loader-pcmcia.o popen.o
SOURCES = $(subst .o,.c,$(OBJS) $(LOADEROBJS))
BINS = init
DIRS = 
NETOBJS = net.o 
ifeq (i386, $(ARCH))
KON = 0
endif
PCMCIAOBJS = pcmcia.o $(NETOBJS)
OPTS = -O2 -g

CFLAGS = $(DEBUG) $(OPTS) -Wall -D_GNU_SOURCE=1 -I/usr/include/rpm -I.. -DUSE_ALT_DNS=1 -DVERSION='"$(VERSION)"' -DHAVE_LIBIO_H -ggdb

ALLOBJS = $(OBJS) $(PCMCIAOBJS)

ifeq (1, $(KON))
DIRS += kon2
OBJS += ./kon2/src/libkon.a ./kon2/src/display.a ./kon2/lib/libgon.a
CFLAGS += -DINCLUDE_KON=1
endif

ifeq (i386, $(ARCH))
BINS += loader-local loader-network loader-pcmcia
DIRS += pcmcia-install
OBJS += stubs.o 
endif

ifeq (alpha, $(ARCH))
BINS += loader
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

ifeq (1, $(KON))
LANGS = ja
else
LANGS = $(shell awk '{ print $$2 }' ../lang-table | grep -v '^en$$')
endif

TR = $(patsubst %,tr/%.tr,$(LANGS))
TRFILES = $(patsubst %,%.tr,$(LANGS))

all: dirs $(BINS) loader.tr

loader.tr: $(TR) ../lang-table
	(cd tr; ls $(TRFILES) | cpio --quiet -Hcrc -o | gzip -9) > $@

loader.po: *.c
	xgettext --default-domain=loader --add-comments \
		--keyword=_ --keyword=N_ *.c

tr/%.tr: ../po/%.po loader.po
	msgmerge $< loader.po | ./simplemot > $@

dirs:
	for n in $(DIRS); do \
	    (cd $$n; make) \
	done

install: all
#	mkdir -p $(DESTDIR)/sbin
#	mkdir -p $(DESTDIR)/etc
#	rm -f $(DESTDIR)/sbin/loader
#	rm -f $(DESTDIR)/sbin/init
#	install -s loader $(DESTDIR)/sbin/loader
#	install -s init $(DESTDIR)/sbin/init
#	install -m 755 ../kudzu/pcitable $(DESTDIR)/etc
#	install -m 644 loader.tr $(DESTDIR)/etc

loader: loader.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
	../kudzu/libkudzu_loader.a ../isys/libisys.a ../balkan/libbalkan.a \
	../isys/modutils/insmod/libmodutils.a    \
	../isys/modutils/util/libutil.a          \
	../isys/modutils/obj/libobj.a            \
	-L../pump -lpump -lrpm -lbz2 -lz -lresolv -lnewt -lslang -lpci

loader-local: loader-local.o $(OBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        ../kudzu/libkudzu_loader.a ../isys/libisys.a ../balkan/libbalkan.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -L ../stubs -L../pump -lpump -lz -lresolv -lnewt -lslang -lpci

loader-network: loader-net.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        ../kudzu/libkudzu_loader.a ../isys/libisys.a ../balkan/libbalkan.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -L../pump -lpump -lrpm -lbz2 -lz -lresolv -lnewt -lslang -lpci

loader-pcmcia: loader-pcmcia.o pcmcia.o popen.o $(OBJS) $(PCMCIAOBJS)
	$(CC) -g $(STATIC) -o $@ loader-pcmcia.o $(OBJS) \
	    $(PCMCIAOBJS) -L pcmcia-install/cardmgr -lcardmgr -lprobe popen.o \
        -lpopt     \
        ../kudzu/libkudzu_loader.a ../isys/libisys.a ../balkan/libbalkan.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -L../pump -lpump -lrpm -lbz2 -lz -lresolv -lnewt -lslang -lpci

loader.o: loader.c
	$(CC) -DINCLUDE_LOCAL -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $^

loader-local.o: loader.c
	$(CC) -DINCLUDE_LOCAL $(CFLAGS) -o $@ -c $^

loader-net.o: loader.c
	$(CC) -DINCLUDE_NETWORK $(CFLAGS) -o $@ -c $^

loader-pcmcia.o: loader.c
	$(CC) -DINCLUDE_PCMCIA -DINCLUDE_LOCAL -DINCLUDE_NETWORK \
	    $(CFLAGS) -o $@ -c $^

init: init.o $(MINILIBC)
	$(CC) $(STATIC) -g $(LDFLAGS) -o $@ init.o $(MINILIBC)

clean: 
	rm -f *.o .depend *~ loader-local loader-network loader.old loader-pcmcia probe modprobe \
	      loader.po loader.tr tr/*.tr loader init
	for n in $(DIRS); do \
	    (cd $$n; make clean) \
	done

depend:
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

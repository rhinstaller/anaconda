DESTDIR = ../../trees/initrd

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

OBJS = stubs.o log.o windows.o modules.o devices.o cdrom.o urls.o kickstart.o
LOADEROBJS = loader.o loader-pcmcia.o popen.o
SOURCES = $(subst .o,.c,$(OBJS) $(LOADEROBJS))
BINS = init
DIRS = 
NETOBJS = net.o
PCMCIAOBJS = pcmcia.o $(NETOBJS)

ALLOBJS = $(OBJS) $(PCMCIAOBJS)

ifeq (i386, $(ARCH))
BINS += loader-local loader-network loader-pcmcia
DIRS += pcmcia-install
endif

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

OPTS = -O2 -g

CFLAGS = $(DEBUG) $(OPTS) -Wall -D_GNU_SOURCE=1 -I/usr/include/rpm -I.. -DUSE_ALT_DNS=1 -DVERSION='"$(VERSION)"'

STATIC = -static

ifeq (i386,$(ARCH))
MINILIBC=minilibc.o
CFLAGS+=-DUSE_MINILIBC=1 -DUSE_LOGDEV
LDFLAGS = -nostdlib /usr/lib/crt1.o
STATIC=-static
else
CFLAGS+=-DUSE_MINILIBC=0
STATIC=
endif

VERSION = 6.0

all: dirs $(BINS)

dirs:
	for n in $(DIRS); do \
	    cd $$n; make; \
	done

install: all
	#mkdir -p $(DESTDIR)/sbin
	#mkdir -p $(DESTDIR)/etc
	#rm -f $(DESTDIR)/sbin/loader
	#rm -f $(DESTDIR)/sbin/init
	#install -s loader $(DESTDIR)/sbin/loader
	#install -s init $(DESTDIR)/sbin/init
	#install -m 755 ../kudzu/pcitable $(DESTDIR)/etc

loader-local: loader-local.o $(OBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        ../kudzu/libkudzu.a ../isys/libisys.a ../balkan/libbalkan.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -lrpm -lbz2 -lz -lresolv -lnewt -lslang -lpci

loader-network: loader-net.o $(OBJS) $(NETOBJS)
	$(CC) -g $(STATIC) -o $@ $^ -lpopt     \
        ../kudzu/libkudzu.a ../isys/libisys.a ../balkan/libbalkan.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -L../pump -lpump -lrpm -lbz2 -lz -lresolv -lnewt -lslang -lpci

loader-pcmcia: loader-pcmcia.o pcmcia.o popen.o $(OBJS) $(PCMCIAOBJS)
	$(CC) -g $(STATIC) -o $@ loader-pcmcia.o $(OBJS) \
	    $(PCMCIAOBJS) -L pcmcia-install/cardmgr -lcardmgr -lprobe popen.o \
        -lpopt     \
        ../kudzu/libkudzu.a ../isys/libisys.a ../balkan/libbalkan.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -L../pump -lpump -lrpm -lbz2 -lz -lresolv -lnewt -lslang -lpci

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
	rm -f *.o .depend *~

depend:
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

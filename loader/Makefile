DESTDIR = ../../trees/initrd

OBJS = loader.o log.o windows.o
SOURCES = $(subst .o,.c,$(OBJS))
BINS = loader init

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

OPTS = -O2 -g

CFLAGS = $(DEBUG) $(OPTS) -Wall -D_GNU_SOURCE=1 -I/usr/include/rpm -I.. -DUSE_ALT_DNS=1

STATIC = -static

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ifeq (i386,$(ARCH))
MINILIBC=minilibc.o
CFLAGS+=-DUSE_MINILIBC=1 -DUSE_LOGDEV -DVERSION='"$(VERSION)"'
LDFLAGS = -nostdlib /usr/lib/crt1.o
STATIC=-static
else
CFLAGS+=-DUSE_MINILIBC=0
STATIC=
endif

VERSION = 6.0

all: $(BINS)

install: all
	mkdir -p $(DESTDIR)/sbin
	mkdir -p $(DESTDIR)/etc
	rm -f $(DESTDIR)/sbin/loader
	rm -f $(DESTDIR)/sbin/init
	install -s loader $(DESTDIR)/sbin/loader
	install -s init $(DESTDIR)/sbin/init
	install -m 755 ../isys/pci/pcitable $(DESTDIR)/etc

loader: $(OBJS)
	$(CC) -g $(STATIC) -o $@ $(OBJS) -lpopt     \
        ../isys/pci/libpciprobe.a ../isys/isys.a \
        ../isys/modutils/insmod/libmodutils.a    \
        ../isys/modutils/util/libutil.a          \
        ../isys/modutils/obj/libobj.a            \
        -lrpm -lz -lresolv -lnewt -lslang -lpci

init: init.o $(MINILIBC)
	$(CC) $(STATIC) -g $(LDFLAGS) -o $@ init.o $(MINILIBC)

clean: 
	rm -f *.o .depend *~

depend:
	$(CPP) $(CFLAGS) -DHAVE_CONFIG_H -M $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

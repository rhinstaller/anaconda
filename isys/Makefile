include ../Makefile.inc

CFLAGS +=  -I$(PYTHONINCLUDE) -I.. -DHAVE_NFS -fno-strict-aliasing

OBJECTS = nfsmount.o nfsmount_clnt.o nfsmount_xdr.o imount.o \
          smp.o devnodes.o cpio.o uncpio.o dasd.o \
          lang.o isofs.o dns.o linkdetect.o vio.o \
          ethtool.o wireless.o eddsupport.o nl.o str.o auditd.o
SOBJECTS = $(patsubst %.o,%.lo,$(OBJECTS))
SOURCES = $(patsubst %.o,%.c,$(OBJECTS)) isys.c
LOADLIBES = -lresolv -lpci -lpopt -lext2fs -lz -lkudzu -lpci -ldevmapper
LOADLIBES += $(SELINUXLIBES)
ifeq ($(USESELINUX),1)
LOADLIBES += -laudit
endif
PYMODULES = _isys.so
SUBDIRS = gzlib

# libdhcp
LOADLIBES += $(shell pkg-config --libs libdhcp)
CFLAGS += $(shell pkg-config --cflags libdhcp)

GENERATED = nfs_mountversion.h

ifeq ($(ARCH),sparc)
PYMODULES += _silo.so
SOURCES += silo.c
endif

ifeq ($(ARCH),ppc)
OBJECTS += minifind.o
SOURCES += minifind.c
endif

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: subdirs $(PYMODULES) libisys.a

%.lo: %.c
	$(CC) -c $(CFLAGS) -fPIC -o $@ $<

_isys.so: isys.lo $(SOBJECTS)
	gcc -shared -g -fPIC -o $@ isys.lo $(SOBJECTS) $(LOADLIBES)

_silo.so: silo.c
	gcc -shared $(CFLAGS) -fpic -o $@ silo.c ../balkan/libbalkan.a

libisys.a: libisys.a($(OBJECTS))

filtertest: filtertest.o libisys.a

clean:
	rm -f *.o *.so *.lo *.a *.pyc $(TARGET) $(SOBJECTS)
	rm -f $(OBJECTS) $(GENERATED)
	rm -f .depend
	rm -f nl
	for d in $(SUBDIRS); do make -C $$d clean; done

install: all
	install -s $(PYMODULES) $(DESTDIR)/$(PYTHONLIBDIR)
	install isys.py $(DESTDIR)/$(PYTHONLIBDIR)

subdirs:
	for d in $(SUBDIRS); do make -C $$d; done

nfsmount.o: nfs_mountversion.h

nfsmount.lo: nfs_mountversion.h

nfsmount.do: nfs_mountversion.h

nfs_mountversion.h: /usr/include/linux/nfs_mount.h
	grep NFS_MOUNT_VERSION $< | sed -e 's/NFS/KERNEL_NFS/' > $@

depend: nfs_mountversion.h
	$(CPP) -M $(CFLAGS) $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           


include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))
CFLAGS = -I/usr/include/python1.5 -I.. -Wall -O2 -g -fPIC -DHAVE_NFS -D_LARGEFILE_SOURCE=1 -D_LARGEFILE64_SOURCE=1

OBJECTS = nfsmount.o dns.o nfsmount_clnt.o nfsmount_xdr.o imount.o \
          smp.o moduleinfo.o devnodes.o cpio.o probe.o uncpio.o \
	  lang.o isofs.o
SOURCES = $(patsubst %.o,%.c,$(OBJECTS)) isys.c
STATICOBJS = otherinsmod.o
LOADLIBES = -lbz2 -lresolv -lz -lpci -lpopt -lpump -lext2fs
PYMODULES = _isys.so
SUBDIRS = modutils

GENERATED = nfs_mountversion.h

ifeq ($(ARCH),sparc)
PYMODULES += _silo.so
SOURCES += silo.c
endif

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: subdirs $(PYMODULES) libisys.a

_isys.so: isys.o $(OBJECTS)
	gcc -shared -g -o $@ isys.o $(OBJECTS) $(LOADLIBES)

_silo.so: silo.c
	gcc -shared $(CFLAGS) -fpic -o $@ silo.c ../balkan/libbalkan.a

libisys.a: libisys.a($(OBJECTS) $(STATICOBJS))

clean:
	rm -f *.o *.so *.a *.pyc $(TARGET) $(OBJECTS) $(GENERATED)
	for d in $(SUBDIRS); do make -C $$d clean; done

install: all
	install -s $(PYMODULES) $(DESTDIR)/$(PYTHONLIBDIR)
	install isys.py $(DESTDIR)/$(PYTHONLIBDIR)

subdirs:
	for d in $(SUBDIRS); do make -C $$d; done

nfsmount.o: nfs_mountversion.h

nfs_mountversion.h: /usr/include/linux/nfs_mount.h
	grep NFS_MOUNT_VERSION $< | sed -e 's/NFS/KERNEL_NFS/' > $@

depend: nfs_mountversion.h
	$(CPP) -M $(CFLAGS) $(SOURCES) > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

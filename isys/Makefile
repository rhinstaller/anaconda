include ../Makefile.inc

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))
CFLAGS = -I/usr/include/python1.5 -I.. -g -DHAVE_NFS -DHAVE_NFSV3
OBJECTS = nfsmount.o dns.o mount_clnt.o nfsmount_xdr.o imount.o \
          smp.o moduleinfo.o devnodes.o cpio.o probe.o uncpio.o
STATICOBJS = otherinsmod.o
STATICLIBS = ../kudzu/kudzumodule.so
LOADLIBES = -lbz2 -lresolv -lz -lpci -lpopt
SUBDIRS = modutils pci
#PYTHONLIBDIR = $(DESTDIR)/Pusr/lib/python1.5/site-packages
PYMODULES = _isys.so

ifeq ($(ARCH),sparc)
PYMODULES += _silo.so
endif

all: subdirs $(PYMODULES) libisys.a

_isys.so: isys.o $(OBJECTS) $(STATICLIBS)
	gcc -shared -g -o $@ isys.o $(OBJECTS) $(STATICLIBS) $(LOADLIBES)

_silo.so: silo.c
	gcc -shared $(CFLAGS) -fpic -o $@ silo.c ../balkan/libbalkan.a

libisys.a: libisys.a($(OBJECTS) $(STATICOBJS))

clean:
	rm -f *.o *.so *.a *.pyc $(TARGET) $(OBJECTS)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

install: all
	cp $(PYMODULES) isys.py $(DESTDIR)/$(PYTHONLIBDIR)

subdirs:
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

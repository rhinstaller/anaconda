CFLAGS = -I/usr/include/python1.5 -I.. -g
OBJECTS = nfsmount.o dns.o mount_clnt.o mount_xdr.o imount.o \
          smp.o moduleinfo.o devnodes.o cpio.o probe.o
STATICOBJS = otherinsmod.o
STATICLIBS = ../kudzu/libkudzu.a
LOADLIBES = -lrpm -lbz2 -lresolv -lz -lpci -lpopt
SUBDIRS = modutils pci
PYTHONLIBDIR = $(DESTDIR)/usr/lib/python1.5/site-packages

all: subdirs _isys.so libisys.a 

_isys.so: isys.o $(OBJECTS) $(STATICLIBS)
	gcc -shared -g -o $@ isys.o $(OBJECTS) $(STATICLIBS) $(LOADLIBES)

libisys.a: libisys.a($(OBJECTS) $(STATICOBJS))

clean:
	rm -f *.o $(TARGET) $(OBJECTS)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

install: all
	cp _isys.so isys.py $(PYTHONLIBDIR)

subdirs:
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

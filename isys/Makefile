CFLAGS = -I/usr/include/python1.5 -g
OBJECTS = isys.o nfsmount.o dns.o mount_clnt.o mount_xdr.o imount.o \
          smp.o moduleinfo.o devnodes.o cpio.o probe.o
STATICOBJS = otherinsmod.o
STATICLIBS = pci/libpciprobe.a
LOADLIBES = -lrpm -lresolv -lz -lpci -lpopt
SUBDIRS = modutils pci
PYTHONLIBDIR = $(DESTDIR)/usr/lib/python1.5/site-packages

all: subdirs _isys.so libisys.a 

_isys.so: $(OBJECTS) $(STATICLIBS)
	gcc -shared -g -o $@ $(OBJECTS) $(STATICLIBS) $(LOADLIBES)

libisys.a: libisys.a($(OBJECTS) $(STATICOBJS))

clean:
	rm -f *.o $(TARGET) $(OBJECTS)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

install: all
	cp _isys.so isys.py $(PYTHONLIBDIR)

subdirs:
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

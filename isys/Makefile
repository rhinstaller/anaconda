DESTDIR = $(TOPDIR)/RedHat/instimage/usr/lib/python1.5/site-packages

CFLAGS = -I/usr/include/python1.5 -g
OBJECTS = isys.o nfsmount.o dns.o mount_clnt.o mount_xdr.o imount.o smp.o \
	  moduleinfo.o devnodes.o
STATICLIBS = pci/libpciprobe.a 
LOADLIBES = -lresolv
SUBDIRS = pci

all: subdirs _isys.so isys.a 

_isys.so: $(OBJECTS) $(STATICLIBS)
	gcc -shared -g -o $@ $(OBJECTS) $(STATICLIBS) $(LOADLIBES)

isys.a: isys.a($(OBJECTS))

clean:
	rm -f *.o $(TARGET) $(OBJECTS)
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d clean; done

install: all
	cp _isys.so isys.py $(DESTDIR)

subdirs:
	for d in $(SUBDIRS); do make TOPDIR=../$(TOPDIR) -C $$d; done

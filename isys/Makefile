DESTDIR = $TOPDIR/RedHat/instimage/usr/lib/python1.5/site-packages

CFLAGS = -I/usr/include/python1.5
OBJECTS = isys.o nfsmount.o dns.o mount_clnt.o mount_xdr.o imount.o
LOADLIBES = -lresolv

all: _isys.so isys.a

_isys.so: $(OBJECTS)
	gcc -shared -o $@ $(OBJECTS) $(LOADLIBES)

isys.a: isys.a($(OBJECTS))

clean:
	rm -f *.o $(TARGET) $(OBJECTS)

install: all
	cp _isys.so isys.py $(DESTDIR)

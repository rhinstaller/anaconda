
CFLAGS = -I/usr/include/python1.5
OBJECTS = isys.o nfsmount.o dns.o mount_clnt.o mount_xdr.o imount.o
LOADLIBES = -lresolv

all: _isys.so

_isys.so: $(OBJECTS)
	gcc -shared -o $@ $(OBJECTS) $(LOADLIBES)

clean:
	rm -f *.o $(TARGET) $(OBJECTS)

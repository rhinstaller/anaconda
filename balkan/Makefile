DESTDIR = $(TOPDIR)/RedHat/instimage/usr/lib/python1.5/site-packages

OBJECTS = rw.o dos.o

TARGET = libbalkan.a

all: $(TARGET) _balkanmodule.so

_balkanmodule.so: _balkanmodule.o libbalkan.a
	gcc -shared -o $@ _balkanmodule.o libbalkan.a

_balkanmodule.o: _balkanmodule.c balkan.h
	gcc $(CFLAGS) -I/usr/include/python1.5 -c -fPIC -o $@ $< 

libbalkan.a: libbalkan.a($(OBJECTS))

clean:
	rm -f *.o $(TARGET)

dos.o: dos.h

install: all
	cp _balkanmodule.so $(DESTDIR)

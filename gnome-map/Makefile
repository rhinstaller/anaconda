include ../Makefile.inc

all: gglobe-canvas timezonemapmodule.so

CFLAGS=-g -O2 -Wall -fPIC `gnome-config --cflags gnomeui` -I/usr/include/python1.5
LDFLAGS=`gnome-config --libs gnomeui`

install: timezonemapmodule.so
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)
	install -s timezonemapmodule.so $(DESTDIR)/$(PYTHONLIBDIR)
	mkdir -p $(DESTDIR)/$(ANACONDADATADIR)/pixmaps
	install map480.png $(DESTDIR)/$(ANACONDADATADIR)/pixmaps

gglobe-canvas: gglobe-canvas.c gnome-map.o gnome-canvas-dot.o gglobe-canvas.o gnome-map.h timezones.o timezones.h
	gcc -O2 -g -o gglobe-canvas gnome-map.o timezones.o gnome-canvas-dot.o gglobe-canvas.o $(LDFLAGS)


timezonemapmodule.so: gnome-map.o gnome-canvas-dot.o timezonemapmodule.o gnome-map.h timezones.o timezones.h
	gcc -g -o timezonemapmodule.so -shared gnome-map.o gnome-canvas-dot.o timezonemapmodule.o timezones.o $(LDFLAGS)

clean:
	rm -f gglobe-canvas *.so *.o *~

depend:

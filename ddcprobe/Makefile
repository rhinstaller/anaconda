CFLAGS=-Wall -O2 -g# -DDEBUG

TARGETS=ddcprobe svgamodes ddcxinfo modetest libvbe.a

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

everything: $(TARGET)

all: $(TARGETS)

install: $(TARGETS)
	cp -a ddcprobe $(DESTDIR)/usr/sbin/ddcprobe

ddcprobe: lrmi.o vesamode.o vbe.o ddcprobe.o

svgamodes: lrmi.o vesamode.o vbe.o svgamodes.o

ddcxinfo: lrmi.o vesamode.o vbe.o ddcxinfo.o

modetest: lrmi.o vesamode.o vbe.o modetest.o

libvbe.a: lrmi.o vesamode.o vbe.o
	$(AR) cru $@ $^

install-lib: $(prefix)/include/vbe.h $(prefix)/lib/libvbe.a

$(prefix)/include/vbe.h:
	install -m 644 vbe.h $(prefix)/include/vbe.h

$(prefix)/lib/libvbe.a:
	install -m 644 libvbe.a $(prefix)/lib/libvbe.a

clean:
	$(RM) $(TARGETS) *.o .depend core

depend:
	$(CPP) -M $(CFLAGS) *.c > .depend

ifeq (.depend,$(wildcard .depend))
include .depend
endif                                           

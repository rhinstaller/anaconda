CFLAGS=-Wall -O -g# -DDEBUG

TARGETS=ddcprobe svgamodes ddcxinfo modetest libvbe.a

all: $(TARGETS)

install: $(TARGETS)
	cp -a ddcprobe $(DESTDIR)/usr/sbin/ddcprobe

ddcprobe: lrmi.o vesamode.o vbe.o ddcprobe.o

svgamodes: lrmi.o vesamode.o vbe.o svgamodes.o

ddcxinfo: lrmi.o vesamode.o vbe.o ddcxinfo.o

modetest: lrmi.o vesamode.o vbe.o modetest.o

libvbe.a: lrmi.o vesamode.o vbe.o
	$(AR) cru $@ $^

#install: $(DESTDIR)/usr/include/vbe.h $(DESTDIR)/usr/lib/libvbe.a

$(DESTDIR)/usr/include/vbe.h:
	install -m 644 vbe.h $(DESTDIR)/usr/include/vbe.h

$(DESTDIR)/usr/lib/libvbe.a:
	install -m 644 libvbe.a $(DESTDIR)/usr/lib/libvbe.a

clean:
	$(RM) $(TARGETS) *.o core

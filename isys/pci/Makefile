CFLAGS = -Wall

libpciprobe.a: libpciprobe.a(pciprobe.o)

pciprobe.c: driverlist.h

driverlist.h: pci.ids unsupported kernel video mergeids
	./mergeids

clean:
	rm -f driverlist.h pciprobe *.o

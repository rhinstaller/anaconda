CFLAGS = -Wall -g
LOADLIBES = libpciprobe.a
LDFLAGS = -g

all: testprobe

libpciprobe.a: libpciprobe.a(pciprobe.o) pcitable 

testprobe: testprobe.o libpciprobe.a

pciprobe.c: pciprobe.h

pcitable: pci.ids unsupported kernel video mergeids
	./mergeids

clean:
	rm -f driverlist.h pciprobe *.o testprobe *.a

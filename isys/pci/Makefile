CFLAGS = -Wall -g
LOADLIBES = -lpci
LDFLAGS = -g

all: testprobe

libpciprobe.a: libpciprobe.a(pciprobe.o)

testprobe: libpciprobe.a pciprobe.c
	$(CC) $(CFLAGS) $(LDFLAGS) -DTESTING pciprobe.c -o testprobe $(LOADLIBES)
	
clean:
	rm -f *.o testprobe *.a core
	
	

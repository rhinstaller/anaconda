include ../Makefile.inc

CFLAGS = -g -fPIC -D_FILE_OFFSET_BITS=64 -I$(PYTHONINCLUDE) -O -Wall -Werror \
	-D_FORTIFY_SOURCE=2
OBJECTS = md5.o libimplantisomd5.o checkisomd5.o pyisomd5sum.c \
	  implantisomd5 checkisomd5
SOURCES = $(patsubst %.o,%.c,$(OBJECTS))
LDFLAGS = -lpopt

PYOBJS = pyisomd5sum.o libcheckisomd5.o libimplantisomd5.o md5.o

ifeq (.depend,$(wildcard .depend))
TARGET=all
else
TARGET=depend all
endif

all: implantisomd5 checkisomd5 pyisomd5sum.so	

%.o: %.c
	gcc -c -O $(CFLAGS) -o $@ $<

implantisomd5: implantisomd5.o md5.o libimplantisomd5.o

checkisomd5: checkisomd5.o md5.o libcheckisomd5.o

pyisomd5sum.so: $(PYOBJS)
	gcc -shared -g -o pyisomd5sum.so -fpic $(PYOBJS)

install:
	install -m 755 implantisomd5 $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 checkisomd5 $(DESTDIR)/$(RUNTIMEDIR)
	install -s pyisomd5sum.so $(DESTDIR)/$(RUNTIMEDIR)

clean:
	rm -f *.o *.lo *.so *.pyc .depend *~
	rm -f implantisomd5 checkisomd5 

depend:
	$(CPP) -M $(CFLAGS) -I$(PYTHONINCLUDE) *.c > .depend


ifeq (.depend,$(wildcard .depend))
include .depend
endif

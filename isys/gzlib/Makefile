include ../../Makefile.inc

CFLAGS += -I . -g
SOURCES = bits.c gzip.c inflate.c lzw.c trees.c unzip.c util.c zip.c binding.c
OBJS = bits.o gzip.o inflate.o lzw.o trees.o unzip.o util.o zip.o binding.o

DOBJS = $(patsubst %.o,%.do,$(OBJS))

ifeq (i386, $(ARCH))
DIETLIB=libgunzip-diet.a($(DOBJS))
endif

all: libgunzip.a($(OBJS)) $(DIETLIB)

clean:	
	rm -f libgunzip.a $(OBJS) $(DOBJS)

%.do: %.c
	diet $(CC) -c $(CFLAGS) -o $@ $<


include ../../Makefile.inc

CFLAGS += -I . -Os -g -Wall
SOURCES = bits.c gzip.c inflate.c lzw.c trees.c unzip.c util.c zip.c binding.c \
	  deflate.c zip.c
OBJS = $(patsubst %.c,%.o,$(SOURCES))
DOBJS = $(patsubst %.o,%.do,$(OBJS))

ifeq (i386, $(ARCH))
DIETLIB=libgunzip-diet.a($(DOBJS))
endif

all: libgunzip.a($(OBJS)) $(DIETLIB) test

test: libgunzip.a test.c
	$(CC) $(CFLAGS) -o test test.c libgunzip.a

clean:	
	rm -f libgunzip.a $(OBJS) $(DOBJS)

%.do: %.c
	diet $(CC) -c $(CFLAGS) -o $@ $<


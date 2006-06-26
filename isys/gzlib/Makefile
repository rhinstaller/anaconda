include ../../Makefile.inc

CFLAGS += -I . -fPIC
SOURCES = bits.c gzip.c inflate.c lzw.c trees.c unzip.c util.c zip.c binding.c \
	  deflate.c zip.c
OBJS = $(patsubst %.c,%.o,$(SOURCES))

all: libgunzip.a($(OBJS)) test

test: libgunzip.a test.c
	$(CC) $(CFLAGS) -o test test.c libgunzip.a

clean:	
	rm -f libgunzip.a $(OBJS)

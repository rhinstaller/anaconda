include ../../Makefile.inc

CC = diet gcc
CFLAGS += -I . -g
SOURCES = bits.c gzip.c inflate.c lzw.c trees.c unzip.c util.c zip.c binding.c
OBJS = bits.o gzip.o inflate.o lzw.o trees.o unzip.o util.o zip.o binding.o

all: libgunzip.a($(OBJS))

clean:	
	rm -f libgunzip.a $(OBJS)

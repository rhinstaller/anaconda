INC = /usr/include
LIB_DIR = /usr/lib
LIBS = $(LIB_DIR)/libbfd.a $(LIB_DIR)/libiberty.a

all: fpswa_version

fpswa_version:fpswa_version.c $(LIBS)
	gcc -g -I$(INC) -o fpswa_version fpswa_version.c $(LIBS)

clean:
	rm -f fpswa_version

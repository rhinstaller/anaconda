
OBJECTS = rw.o dos.o
CFLAGS += -I/usr/include/rpm -I/usr/include/python1.5

TARGET = rpmmodule.so

all: $(TARGET) 

rpmmodule.so: rpmmodule.o 
	gcc -shared -o $@ rpmmodule.o -lrpm -lz -ldb

clean:
	rm -f *.o $(TARGET)

DESTDIR = $(TOPDIR)/RedHat/instimage/usr/lib/python1.5/site-packages

CFLAGS += -I/usr/include/rpm -I/usr/include/python1.5 -g

TARGET = rpmmodule.so

all: $(TARGET) 

rpmmodule.so: rpmmodule.o 
	gcc -shared -o $@ rpmmodule.o -lrpm -lz -ldb1

clean:
	rm -f *.o $(TARGET)

install: all
	cp $(TARGET) $(DESTDIR)

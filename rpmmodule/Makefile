PYTHONLIBDIR = $(DESTDIR)/usr/lib/python1.5/site-packages

CFLAGS += -fPIC -I/usr/include/rpm -I/usr/include/python1.5 -g

TARGET = rpmmodule.so

all: $(TARGET) 

rpmmodule.so: rpmmodule.o upgrade.o hash.o
	gcc -shared -o $@ $^ -lrpm -lz -ldb1

clean:
	rm -f *.o $(TARGET)

install: all
	mkdir -p $(PYTHONLIBDIR)
	cp $(TARGET) $(PYTHONLIBDIR)

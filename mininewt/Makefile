
include ../Makefile.inc

LIBS = -lslang -lm #-lefence
SHLIBS = -lslang -lm -lc

GPM_SUPPORT=

CFLAGS = -Os -I/usr/include/slang

VERSION = 0.51.0
CVSTAG = r$(subst .,-,$(VERSION))
SONAME = 0.51

PYTHONVERS = $(shell ls -d /usr/include/python* | sed "s|/usr/include/||g")

OBJS = newt.o button.o form.o checkbox.o entry.o label.o listbox.o \
          scrollbar.o textbox.o scale.o grid.o windows.o buttonbar.o \
	  checkboxtree.o
SOBJS = $(patsubst %.o,%.lo,$(OBJS))
DOBJS = $(patsubst %.o,%.do,$(OBJS))
PROGS = 
LIBNEWT = libnewt.a($(OBJS))
ifeq (i386, $(ARCH))
LIBNEWT=libnewt-diet.a($(DOBJS))
endif
LIBNEWTSH = libnewt.so.$(VERSION)
LIBNEWTSONAME = libnewt.so.$(SONAME)

SHCFLAGS = -fPIC


#--------------------------------------

SOURCES = $(subst .o,.c,$(TESTOBJS) $(OBJS))

ifeq (.depend,$(wildcard .depend))
TARGET=$(PROGS)
else
TARGET=depend $(PROGS)
endif

all: $(LIBNEWTSH) $(LIBNEWT) _snackmodule.so

_snackmodule.so:   snackmodule.c $(LIBNEWTSH)
	for ver in $(PYTHONVERS) ; do \
	    if [ ! -f "$$ver/_snackmodule.so" -o $(LIBNEWTSH) -nt "$$ver/_snackmodule.so" ]; then \
	    	mkdir -p $$ver ;\
	        gcc $(CFLAGS) -I/usr/include/$$ver -fPIC -c -o $$ver/snackmodule.o snackmodule.c ;\
		gcc --shared $(SHCFLAGS) -o $$ver/_snackmodule.so $$ver/snackmodule.o -L . $(LIBNEWTSH) ;\
	    fi ; \
	done

veryclean: clean
	rm -f .depend

clean:
	rm -f $(PROGS) *.o *.lo *.do *.so* *.a 

depend:
	$(CPP) $(CFLAGS) -M $(SOURCES) > .depend

$(SHAREDDIR):
	mkdir -p $(SHAREDDIR)

sharedlib: $(LIBNEWTSH)

$(LIBNEWTSH): $(SOBJS)
	gcc -shared -o $(LIBNEWTSH) -Wl,-soname,$(LIBNEWTSONAME) $(SOBJS) $(SHLIBS)

%.do: %.c
	diet $(CC) -c $(CFLAGS) -o $@ $<

%.lo: %.c
	$(CC) $(SHCFLAGS) -c $(CFLAGS) -o $@ $<

newt.o: newt.c Makefile
	$(CC) $(CFLAGS) -DVERSION=\"$(VERSION)\" -c -o $@ $<

newt.do: newt.c Makefile
	diet $(CC) $(SHCFLAGS) $(CFLAGS) -DVERSION=\"$(VERSION)\" -c -o $@ $<

newt.lo: newt.c Makefile
	$(CC) $(SHCFLAGS) $(CFLAGS) -DVERSION=\"$(VERSION)\" -c -o $@ $<


install: $(LIBNEWT) $(LIBNEWTSH) _snackmodule.so
	install -s -m 755 $(LIBNEWTSH) $(DESTDIR)/$(RUNTIMEDIR)/$(LIBNEWTSONAME)
	for ver in $(PYTHONVERS) ; do \
	   install -s -m 755 $$ver/_snackmodule.so $(DESTDIR)/$(RUNTIMEDIR)
	done

ifeq (.depend,$(wildcard .depend))
include .depend
endif

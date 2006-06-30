PACKAGE = wlite
VERSION = 0.8.1

prefix      := /usr/local
exec_prefix := $(prefix)
libdir      := $(exec_prefix)/lib
includedir  := $(prefix)/include

.PHONY: all
.PHONY: check
.PHONY: install installdirs install-strip uninstall
.PHONY: clean distclean maintainer-clean mostlyclean
.PHONY: dist

###############################################################################

ifdef SMALL
   CDFLAGS += -DWLITE_EXTENSIONS=0
   CDFLAGS += -DWLITE_AMBI_LOCALE=0
   CDFLAGS += -DWLITE_ENVIRONMENT=0
endif

ifndef LARGE
   CDFLAGS += -DWLITE_XBMP_CHAR=0
endif

ifdef DEBUG
   CFLAGS   = -O0 -g -Wall
   ifeq "dmalloc" "$(DEBUG)"
      CDFLAGS += -DDMALLOC_FUNC_CHECK=1
      LDFLAGS  = -ldmalloc
   endif
   ifeq "efence" "$(DEBUG)"
      LDFLAGS  = -lefence
   endif
else
   CFLAGS   = -Os -Wall
   CDFLAGS += -DNDEBUG
endif

architecture := $(shell uname -m)
ifneq (,$(filter x86_64 s390 s390x ppc sparc,$(architecture)))
override CFLAGS += -fPIC
endif

ifeq "diet" "$(basename $(firstword $(CC)))"
   FATCC = $(wordlist 2,$(words $(CC)),$(CC))
   FATCFLAGS = $(CFLAGS) -std=gnu99
else
   override CFLAGS += -std=gnu99
   FATCC = $(CC)
   FATCFLAGS = $(CFLAGS)
endif

override CFLAGS += $(CDFLAGS)

libraries  = libwlite.a
unicodeorg = CaseFolding.txt EastAsianWidth.txt UnicodeData.txt
tests      = test-wcwidth test-string test-stdlib
includes   = wlite_config.h wlite_wchar.h wlite_wctype.h wlite_stdlib.h
functions  = $(wildcard wlite_*.c)
sources    = to_c.c to_c.h $(functions) $(addsuffix .c,$(tests) $(to_c))
members    = wcmp.o $(patsubst %.c,%.o,$(functions) $(c_unidata))
objects    = to_c.o wcmp.o $(to_c) $(tests)
archives   = $(PACKAGE)-$(VERSION).tar.gz
makefiles  = $(wildcard *[mM]akefile)
unidata    = $(addsuffix .dat,$(unicodeorg))
c_unidata  = $(patsubst %.txt.dat,%.dat.c,$(unidata))
to_c       = $(patsubst %.txt.dat,to_c-%,$(unidata))
charset_in = $(wildcard test.*.txt)
utf8_out   = $(patsubst test.%.txt,%.utf-8.txt,$(charset_in))

.INTERMEDIATE: $(c_unidata)

libwlite.a: libwlite.a($(members))
libwlite.a(wcmp.o): wcmp.c $(includes)
libwlite.a(wlite_%.o): wlite_%.c $(includes)
libwlite.a(CaseFolding.dat.o): CaseFolding.dat.c $(includes)
libwlite.a(EastAsianWidth.dat.o): EastAsianWidth.dat.c $(includes)
CaseFolding.dat.c: to_c-CaseFolding CaseFolding.txt.dat $(includes)
EastAsianWidth.dat.c: to_c-EastAsianWidth EastAsianWidth.txt.dat $(includes)
UnicodeData.dat.c: to_c-UnicodeData UnicodeData.txt.dat $(includes)
to_c-CaseFolding: to_c-CaseFolding.c wcmp.o to_c.o $(includes)
to_c-EastAsianWidth: to_c-EastAsianWidth.c wcmp.o to_c.o $(includes)
to_c-UnicodeData: to_c-UnicodeData.c wcmp.o to_c.o $(includes)
to_c.o: to_c.c to_c.h $(includes)
	$(FATCC) $(FATCFLAGS) -c -o $@ $<
$(archives):  $(unidata) $(sources) $(charset_in) $(includes)
$(includes): $(makefiles)

test-wcwidth: test-wcwidth.c $(libraries)
test-string: test-string.c $(libraries)
test-stdlib: test-stdlib.c $(libraries)

TAGS tags: $(sources)
	-etags $(filter %.c,$^)
	-ctags $(filter %.c,$^)

%.h: $(makefiles)
	sed -e "s/\(\$$package\>\)[^$$]*/\1: $(PACKAGE) /gI" \
	    -e "s/\(\$$version\>\)[^$$]*/\1: $(VERSION) /gI" $@ > $@.tmp
	mv $@.tmp $@
%: %.c
	$(FATCC) $(FATCFLAGS) $(LDFLAGS) -o $@ $(filter %.c %.o %.a,$^)
%.dat.c: %.txt.dat
	cat $(filter %.txt.dat,$^) | \
	$(CURDIR)/$(patsubst %.dat.c,to_c-%,$@) > $@ 2> /dev/null
%.utf-8.txt: test.%.txt
	iconv -f $* -t $(subst .,,$(suffix $(basename $@))) < $< > $@
%.exclude:
	echo $(notdir $(CURDIR))/$@ > $@
	for x in $(wildcard $@ RCS .[^.]* *.tar.*); \
	do echo $(notdir $(CURDIR))/$${x} >> $@; \
	done
	echo $(notdir $(CURDIR))/$(basename $@).tar >> $@
%.tar: %.exclude
	tar cv -C .. -X $< -f $@ $(notdir $(CURDIR))
%.tar.bz2: %.tar
	bzip2 -9 -c $< > $@
%.tar.gz: %.tar
	gzip -9 -c $< > $@

all: $(libraries)
check: $(tests) $(utf8_out)
	for test in $(filter $(tests),$+); \
	do cat $(filter $(utf8_out),$+) | ./$${test}; \
	done
clean: mostlyclean
	$(RM) $(libraries) $(utf8_out)
dist: maintainer-clean
	$(MAKE) $(archives)
distclean: clean
	$(RM) $(members) $(c_unidata)
maintainer-clean: distclean
	$(RM) $(archives) TAGS tags $(wildcard core core.*) $(wildcard *.tmp)
mostlyclean:
	$(RM) $(objects)

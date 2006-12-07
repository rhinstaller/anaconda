#
# define destination locations
#
PYTHONLIBDIR = /usr/lib/anaconda
RUNTIMEDIR = /usr/lib/anaconda-runtime
ANACONDADATADIR = /usr/share/anaconda
PYVER  := $(shell python -c 'import sys; print sys.version[0:3]')
PYTHON = python$(PYVER)
PYTHONINCLUDE = /usr/include/$(PYTHON)

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))
ARCH := $(patsubst ppc%,ppc,$(ARCH))
FULLARCH := $(shell uname -m)

ifneq (,$(filter ppc64 x86_64 s390x,$(FULLARCH)))
LIBDIR = lib64
else
LIBDIR = lib
endif

USESELINUX=1

ifeq ($(USESELINUX),1)
SELINUXLIBES = -lselinux -lsepol
SELINUXFLAGS = -DUSESELINUX=1
endif

ifndef RPM_OPT_FLAGS
RPM_OPT_FLAGS = -O2 -g -pipe -Wp,-D_FORTIFY_SOURCE=2 -fexceptions
endif

CFLAGS = $(RPM_OPT_FLAGS) -Wall -Werror -D_GNU_SOURCE=1 -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE=1 -D_LARGEFILE64_SOURCE=1 $(SELINUXFLAGS)

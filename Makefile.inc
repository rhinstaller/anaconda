#
# define destination locations
#
VERSION = 10.0
RELEASE = 3.1
TIMESTAMP := $(shell date "+.%Y%m%d%H%M%S")
SNAPRELEASE := $(RELEASE)$(TIMESTAMP)

PYTHONLIBDIR = /usr/lib/anaconda
RUNTIMEDIR = /usr/lib/anaconda-runtime
ANACONDADATADIR = /usr/share/anaconda
PYTHON = python2.3
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

# diet defines
USEDIET=0
ifeq (i386, $(ARCH))
USEDIET=1
endif

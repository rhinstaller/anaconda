#
# define destination locations
#
VERSION = 8.0.94
RELEASE = 0
TIMESTAMP := $(shell date "+.%Y%m%d%H%M%S")
SNAPRELEASE := $(RELEASE)$(TIMESTAMP)

PYTHONLIBDIR = /usr/lib/anaconda
RUNTIMEDIR = /usr/lib/anaconda-runtime
ANACONDADATADIR = /usr/share/anaconda
PYTHON = python2.2
PYTHONINCLUDE = /usr/include/python2.2

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))
ARCH := $(patsubst ppc%,ppc,$(ARCH))

LIBDIR = lib
ifeq (x86_64, $(ARCH))
LIBDIR = lib64
endif
ifeq (ppc64, $(ARCH))
LIBDIR = lib64
endif
ifeq (s390x, $(ARCH))
LIBDIR = lib64
endif

# diet defines
USEDIET=0
ifeq (i386, $(ARCH))
USEDIET=1
endif

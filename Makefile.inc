#
# define destination locations
#
VERSION = 9.1
RELEASE = 1.RHEL
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

#
# define destination locations
#
VERSION = 8.0.93
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

ifneq (x86_64, $(ARCH))
LIBDIR = lib
else
LIBDIR = lib64
endif

# diet defines
USEDIET=0
ifeq (i386, $(ARCH))
USEDIET=1
endif
# do we really want to use diet on ppc?
ifeq (ppc, $(ARCH))
USEDIET=1
endif

# define product name to be imported into the loader and anywhere else
# that needs the proper name of the product
PRODUCTNAME="Red Hat Linux"


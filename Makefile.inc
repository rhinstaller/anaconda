#
# define destination locations
#
VERSION = 8.0.92
RELEASE = 8
SNAPRELEASE = $(RELEASE)$(shell date "+.%Y%m%d%H%M")

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

#
# define options
#
JAPANESE=1

# define product name to be imported into the loader and anywhere else
# that needs the proper name of the product
PRODUCTNAME="Red Hat Linux"


#
# define destination locations
#
VERSION = 7.3.93
RELEASE = 2
SNAPRELEASE = $(RELEASE)$(shell date "+.%Y%m%d%H%M")

PYTHONLIBDIR = /usr/lib/anaconda
RUNTIMEDIR = /usr/lib/anaconda-runtime
ANACONDADATADIR = /usr/share/anaconda
PYTHON = python2.2
PYTHONINCLUDE = /usr/include/python2.2

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

#
# define options
#
JAPANESE=1

# define product name to be imported into the loader and anywhere else
# that needs the proper name of the product
PRODUCTNAME="Red Hat Linux"


#
# define destination locations
#

PYTHONLIBDIR = /usr/lib/anaconda
RUNTIMEDIR = /usr/lib/anaconda-runtime
ANACONDADATADIR = /usr/share/anaconda

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

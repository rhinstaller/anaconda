#
# define destination locations
#

PYTHONLIBDIR = /usr/lib/anaconda
RUNTIMEDIR = /usr/lib/anaconda-runtime
ANACONDADATADIR = /usr/share/anaconda
PYTHON = python1.5
PYTHONINCLUDE = /usr/include/python1.5

ARCH := $(patsubst i%86,i386,$(shell uname -m))
ARCH := $(patsubst sparc%,sparc,$(ARCH))

#
# define options
#
JAPANESE=1

# define product name to be imported into the loader and anywhere else
# that needs the proper name of the product
PRODUCTNAME="Red Hat Linux"

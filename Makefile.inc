#
# Makefile.inc
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

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

# uncomment to build 32bit on an 64bit host
#M32FLAGS = -m32
CFLAGS = $(RPM_OPT_FLAGS) -Wall -Werror -D_GNU_SOURCE=1 -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE=1 -D_LARGEFILE64_SOURCE=1 $(SELINUXFLAGS) $(M32FLAGS)
LDFLAGS = $(M32FLAGS)

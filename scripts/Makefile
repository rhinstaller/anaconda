##
##
## Simple makefile for building a Linux kernel module outside
## the kernel source tree.
## Copyright 2000 Jeff Garzik
##
##

##
## Your kernel source tree...
##

MODULE=         xircom_cb



# standard location of source tree.  Make sure no spaces/tabs
# at the end of the line!
TOPDIR=/lib/modules/`uname -r`/build

# jgarzik's kernel source tree
# TOPDIR=/spare/cvs/linux_2_4



KINCLUDES=      $(TOPDIR)/include


#
# Choose only i386, i486, i586, or i686 here.  And your gcc compiler
# may not support i586 or i686, so make sure...
#

CPUFLAGS=       -march=`uname -m`

#
# It is always recommended to use CONFIG_MODVERSIONS where possible.
# If you do not use CONFIG_MODVERSIONS, comment out the line below.
#

MODVERSIONS=    -DMODVERSIONS -include $(KINCLUDES)/linux/modversions.h


LD=             ld
CC=             gcc

CFLAGS= \
        -D__KERNEL__ -I$(KINCLUDES) $(CPUFLAGS) \
        -Wall -Wstrict-prototypes -Werror \
        -O2 -fomit-frame-pointer -fno-strict-aliasing -pipe \
        -mpreferred-stack-boundary=2 \
        -DMODULE $(MODVERSIONS)

OBJS=           


default::       all

all::           $(MODULE).o

checkdep:
        @if [ ! -f .depend ]; then make dep ; make ; exit 0; fi

clean:
        rm -f .depend $(OBJS) $(MODULE).o

dep:
        $(CC) $(CFLAGS) -M *.c > .depend

ifneq ($(wildcard .depend),)
include .depend
endif



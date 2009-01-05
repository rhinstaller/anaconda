#
# Makefile
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

include ../Makefile.inc

ifeq (i386, $(ARCH))
CLASSES = $(shell ls *.py)
else
CLASSES = $(shell ls *.py | grep -v laptop)
endif

all:
	echo "nothing to make"

install: 
	mkdir -p $(DESTDIR)/$(PYTHONLIBDIR)/installclasses
	install -p -m 644 $(CLASSES) $(DESTDIR)/$(PYTHONLIBDIR)/installclasses
	../py-compile --basedir $(DESTDIR)/$(PYTHONLIBDIR)/installclasses $(DESTDIR)/$(PYTHONLIBDIR)/installclasses/*.py

clean:
	rm -f *.o *.so *.pyc

depend:

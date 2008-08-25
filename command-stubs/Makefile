#
# Makefile
#
# Copyright (C) 2007, 2008 Red Hat, Inc.  All rights reserved.
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

STUBS = raidstart-stub raidstop-stub list-harddrives-stub \
	loadkeys-stub losetup-stub mknod-stub syslogd-stub

all:
	@echo "Nothing to do"

depend:
	@echo "Nothing to do"

clean:
	/bin/rm -f *.pyc *~

install:
	for i in $(STUBS) ; do \
		install -m 755 $$i $(DESTDIR)/$(PYTHONLIBDIR) ; \
	done

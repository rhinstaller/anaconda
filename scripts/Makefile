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

all:

install:
	install -m 755 upd-instroot $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 mk-images* $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 buildinstall $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 buildinstall.functions $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 scrubtree $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 getkeymaps $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 makestamp.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 maketreeinfo.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 pyrc.py $(DESTDIR)/$(RUNTIMEDIR)
	install -m 755 upd-updates $(DESTDIR)/$(RUNTIMEDIR)

depend:

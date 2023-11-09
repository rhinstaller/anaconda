# scripts/Makefile.am for anaconda
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

scriptsdir = $(libexecdir)/$(PACKAGE_NAME)
dist_scripts_SCRIPTS = run-anaconda anaconda-pre-log-gen log-capture start-module apply-updates

dist_noinst_SCRIPTS  = makeupdates makebumpver

dist_bin_SCRIPTS = anaconda-cleanup anaconda-disable-nm-ibft-plugin \
                   anaconda-nm-disable-autocons run-in-new-session.py

miscdir = $(datadir)/$(PACKAGE_NAME)

MAINTAINERCLEANFILES = Makefile.in

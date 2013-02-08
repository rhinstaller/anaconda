# systemd/Makefile.am for anaconda
#
# Copyright (C) 2011  Red Hat, Inc.
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
#
# Author: Chris Lumens <clumens@redhat.com>

systemddir = $(prefix)/lib/systemd/system
generatordir = $(prefix)/lib/systemd/system-generators

dist_systemd_DATA = anaconda.service \
		    anaconda-direct.service \
		    anaconda.target \
		    anaconda-tmux@.service \
		    anaconda-shell@.service \
		    instperf.service \
		    anaconda-sshd.service

dist_generator_SCRIPTS = anaconda-generator

MAINTAINERCLEANFILES = Makefile.in

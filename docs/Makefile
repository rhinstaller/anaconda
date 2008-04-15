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

all: command-line.txt kickstart-docs.txt

command-line.txt:
	curl -A "anaconda-build" -o command-line.txt "http://fedoraproject.org/wiki/Anaconda/Options?action=raw"

kickstart-docs.txt:
	curl -A "anaconda-build" -o kickstart-docs.txt "http://fedoraproject.org/wiki/Anaconda/Kickstart?action=raw"

clean:
	rm -rf kickstart-docs.txt command-line.txt api *.xml

depend:

install:

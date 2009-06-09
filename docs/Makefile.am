# docs/Makefile.am for anaconda
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
#
# Author: David Cantrell <dcantrell@redhat.com>

EXTRA_DIST = install-methods.txt mediacheck.txt anaconda-release-notes.txt \
             lvm_sanity_checks.txt rescue-mode api.cfg making-screenshots \
             threads.txt command-line.txt kickstart-docs.txt gettext.txt

CLEANFILES = api *.xml

MAINTAINERCLEANFILES = Makefile.in command-line.txt kickstart-docs.txt

command-line.txt:
	curl -A "anaconda-build" -o command-line.txt "http://fedoraproject.org/w/index.php?title=Anaconda_Boot_Options&action=raw"

kickstart-docs.txt:
	curl -A "anaconda-build" -o kickstart-docs.txt "http://fedoraproject.org/w/index.php?title=Anaconda/Kickstart&action=raw"

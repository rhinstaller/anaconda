#
# Copyright (C) 2020  Red Hat, Inc.
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

SUBDIRS = hmc cdrom repo_files nfs url harddrive cdn closest_mirror rpm_ostree \
    rpm_ostree_container flatpak live_image live_os live_tar repo_path

pkgpythondir = $(pythondir)/py$(PACKAGE_NAME)
payload_moduledir = $(pkgpythondir)/modules/payloads/source
dist_payload_module_DATA = $(wildcard $(srcdir)/*.py)

MAINTAINERCLEANFILES = Makefile.in

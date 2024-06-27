# dracut/Makefile.am for anaconda
#
# Copyright (C) 2012 Red Hat, Inc.
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

SUBDIRS = dd

dracutdir = $(prefix)/lib/dracut/modules.d/80$(PACKAGE_NAME)
dist_dracut_SCRIPTS = module-setup.sh \
                      python-deps \
                      kickstart_version.py \
                      anaconda-lib.sh \
                      parse-anaconda-options.sh \
                      parse-anaconda-repo.sh \
                      parse-anaconda-kickstart.sh \
                      parse-anaconda-net.sh \
                      repo-genrules.sh \
                      kickstart-genrules.sh \
                      updates-genrules.sh \
                      anaconda-ks-sendheaders.sh \
                      anaconda-netroot.sh \
                      anaconda-diskroot \
                      anaconda-hmcroot \
                      anaconda-copy-ks.sh \
                      anaconda-copy-cmdline.sh \
                      anaconda-copy-dhclient.sh \
                      anaconda-copy-prefixdevname.sh \
                      anaconda-copy-s390ccwconf.sh \
                      anaconda-ifcfg.sh \
                      anaconda-set-kernel-hung-timeout.sh \
                      anaconda-error-reporting.sh \
                      fetch-kickstart-net.sh \
                      fetch-kickstart-disk \
                      fetch-updates-disk \
                      parse-kickstart \
                      anaconda-modprobe.sh \
                      save-initramfs.sh \
                      anaconda-pre-shutdown.sh \
                      parse-anaconda-dd.sh \
                      fetch-driver-net.sh \
                      driver-updates-genrules.sh \
                      anaconda-depmod.sh \
                      find-net-intfs-by-driver \
                      anaconda-ifdown \
                      driver_updates.py \
                      anaconda-nfsrepo-cleanup.sh

dist_dracut_DATA = driver-updates@.service

MAINTAINERCLEANFILES = Makefile.in

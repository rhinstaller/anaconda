#!/bin/bash
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>

if [[ $# != 3 ]]; then
    echo "usage: $0 <boot.iso> <resultdir> <repo URL>"
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "Required boot.iso does not exist."
    exit 2
fi

if [ -d "$2" ]; then
    echo "results dir should not already exist."
    exit 3
fi

if [ ! -e /usr/share/lorax ]; then
    echo "Required lorax templates do not exist.  Install the lorax package?"
    exit 4
fi

if [ ! -e anaconda-autogui-testing.ks ]; then
    echo "anaconda-autogui-testing.ks not found."
    exit 5
fi

ISO="$1"
RESULTSDIR="$2"
REPO="$3"

# While we can remove a lot of the dumb defaults we inherit from the spin
# kickstart files by overriding them with other kickstart commands, some
# things we can't.  The following sed lines take care of these:
#
# (1) Remove the first two / partitions we inherit.
# (2) Remove rawhide as a repo because it's already the installation source.
# (3) Don't remove /boot/initramfs*.  Do what now?
ksflatten -c anaconda-autogui-testing.ks | sed -e '\|part /.*--size=3.*|,+1 d' \
                                               -e '/repo --name="rawhide"/ d' \
                                               -e '/^# save a little/,+1 d' > livecd.ks

# Add a repo location for the updated anaconda RPMs.
echo -e "\nrepo --name=updated-anaconda --baseurl=${REPO}\n" >> livecd.ks

# And then we want to use our own lorax template files in order to adjust
# the boot configuration:
#
# (1) Shorten the timeout by a bunch.
# (2) Change the default boot target away from media check.
TEMPLATES=$(mktemp -d)
cp -r /usr/share/lorax/* ${TEMPLATES}
sed -i -e 's/timeout 600/timeout 60/' \
       -e '/label linux/ a\
  menu default' \
       -e '/menu default/ d' ${TEMPLATES}/live/config_files/x86/isolinux.cfg

livemedia-creator --make-iso \
                  --iso "${ISO}" \
                  --title Fedora \
                  --project Fedora \
                  --releasever 21 \
                  --tmp /var/tmp \
                  --resultdir "${RESULTSDIR}" \
                  --ks livecd.ks \
                  --vnc vnc \
                  --lorax-templates ${TEMPLATES} \
                  --ram 2048 \
                  --vcpus 2 \
                  --kernel-args nomodeset \
                  --timeout 90
rm livecd.ks
rm -r ${TEMPLATES}

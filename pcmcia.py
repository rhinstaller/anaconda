#
# pcmcia.py: pcmcia probe and config file generation
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil, string, os, kudzu

import logging
log = logging.getLogger("anaconda")

def pcicType(test = 0):
    devs = kudzu.probe(kudzu.CLASS_SOCKET, kudzu.BUS_PCI, 0)
    if devs:
	log.info("Found a pcic controller of type: yenta_socket")
	return "yenta_socket"

    # lets look for non-PCI socket controllers now
    devs = kudzu.probe(kudzu.CLASS_SOCKET, kudzu.BUS_MISC, 0)

    if devs and devs[0].driver not in ["ignore", "unknown", "disabled"]:
	log.info("Found a pcic controller of type: %s", devs[0].driver)
	return devs[0].driver

    log.info("No pcic controller detected")
    return None

def createPcmciaConfig(path, test = 0):
    f = open(path, "w")

    pcic = pcicType(test = test)

    if (pcic):
	f.write("PCMCIA=yes\n")
	f.write("PCIC=%s\n" % (pcic,))
    else:
	f.write("PCMCIA=no\n")
	f.write("PCIC=\n")

    f.write("PCIC_OPTS=\n")
    f.write("CORE_OPTS=\n")

    f.close()

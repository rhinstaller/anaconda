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

def pcicType(test = 0):
    devs = kudzu.probe(kudzu.CLASS_SOCKET, kudzu.BUS_PCI, 0)
    if devs:
	return "yenta_socket"

    loc = "/sbin/probe"
    if not os.access(loc, os.X_OK):
	loc = "/usr/sbin/probe"

    try:
        result = iutil.execWithCapture(loc, [ loc ])
    except RuntimeError:
        return None


    # VERY VERY BAD - we're depending on the output of /sbin/probe
    # to guess the PCMCIA controller.  Output has changed over the
    # years and this tries to catch cases we know of
    if (string.find(result, "TCIC-2 probe: not found") != -1):
	return None
    elif (string.find(result, "TCIC-2") != -1):
	if (string.find(result, "not") == -1):
	    return "tcic"
	else:
	    return None

    return "i82365"

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

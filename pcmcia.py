#!/usr/bin/python

import iutil, string, os

def hasPcmcia(test = 0):
    loc = "/sbin/probe"
    if not os.access(loc, os.X_OK):
	loc = "/usr/sbin/probe"

    try:
        result = iutil.execWithCapture(loc, [ loc ])
    except RuntimeError:
        return None

    if (string.find(result, "TCIC-2 probe: not found") != -1):
	return None

    return 1

def createPcmciaConfig(path, pcic, test = 0):
    f = open(path, "w")

    if (pcic):
	f.write("PCMCIA=yes\n")
	f.write("PCIC=%s\n" % (pcic,))
    else:
	f.write("PCMCIA=no\n")
	f.write("PCIC=\n")

    f.write("PCIC_OPTS=\n")
    f.write("CORE_OPTS=\n")

    f.close()

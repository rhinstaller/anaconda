#!/usr/bin/python

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

    if (string.find(result, "TCIC-2 probe: not found") != -1):
	return None
    elif (string.find(result, "TCIC-2") != -1):
	return "tcic"

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

#!/usr/bin/python

import iutil, string

def pcicType(test = 0):
    if (test):
	loc = "/sbin/probe"
    else:
	loc = "/usr/sbin/probe"

    result = iutil.execWithCapture(loc, [ loc ])

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

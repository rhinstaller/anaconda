#!/usr/bin/python

import iutil, string, os, kudzu

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

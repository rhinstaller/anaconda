#!/usr/bin/python

import iutil, string

def pcmciaPcicType(test = 0):
    if (test):
	loc = "/sbin/probe"
    else:
	loc = "/usr/sbin/probe"

    result = iutil.execWithCapture(loc, [ loc ])

    if (not string.find("result", "TCIC-2 probe: not found")):
	return None
    elif (not string.find("result", "TCIC-2")):
	return "tcic"

    return "i82365"


#!/usr/bin/python

import iutil, string

def pcmciaPcicType(test = 0):
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


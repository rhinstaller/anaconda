#!/usr/bin/python
import string
import os

def getConfigFile():
    import string

    if os.access("custom/anaconda.conf", os.O_RDONLY):
        f = open("custom/anaconda.conf", "r")
    elif os.access("/tmp/product/anaconda.conf", os.O_RDONLY):
        f = open("/tmp/product/anaconda.conf", "r")
    elif os.access("/tmp/updates/anaconda.conf", os.O_RDONLY):
        f = open("/tmp/updates/anaconda.conf", "r")
    elif os.access("/usr/share/anaconda/custom/anaconda.conf", os.O_RDONLY):
        f = open("/usr/share/anaconda/custom/anaconda.conf", "r")
    elif os.access("anaconda.conf", os.O_RDONLY):
        f = open("anaconda.conf", "r")
    else:
        f = open("/usr/share/anaconda/anaconda.conf", "r")

    lines = f.readlines()
    f.close()

    dict = {}

    for line in lines:
        line = string.strip(line)

        if string.find (line, "#") > -1 or line == "": 
            pass
        else:
            tokens = string.split(line)
            str = string.join(tokens[1:])
            dict[tokens[0]] = str
    return dict

#!/usr/bin/python
import string

def getConfigFile():
    import string

    f = open("anaconda.conf", "r")
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

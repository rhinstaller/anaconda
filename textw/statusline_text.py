import string
import copy

class CleanStatusLine:

    def centerLabel(self, str, space):
        return string.center(str, space)

    def formatStatusLine(self, args):
        if len(args) == 1:
            return self.centerLabel(args[0], self.width)

        nonspaces = 0
        for i in args:
            nonspaces = nonspaces + len(i)

        spaceEach = (self.width-nonspaces)/len(args)
        outstr = ""

        j = 0
        for i in args:
            str = self.centerLabel(i, len(i) + spaceEach)
            outstr = outstr + str
            j = j + 1
            if j != len(args):
                outstr = outstr + "|"

        return outstr

    def setdefaultStatusLine(self, rargs, largs):
        self.rargs = rargs
        self.largs = largs
        

#    def defaultStatusLine(self):
#    def __str__(self):
#        args = copy.deepcopy(self.largs)
#        args.extend(self.rargs)
#        return self.formatStatusLine(args)
        
#    def customStatusLine(self, optargs):
    def __str__(self):
        args = copy.deepcopy(self.largs)
        if self.optargs != None:
            args.extend(optargs)
        args.extend(self.rargs)
        return self.formatStatusLine(args)


    def __init__(self, args, optargs=None):
#        self.largs = ["<Tab>/<Alt-Tab> between elements"]
#        self.rargs = ["<F12> next screen"]
        (self.largs, self.rargs) = args
        self.optargs = optargs
            
        self.width = 80
        

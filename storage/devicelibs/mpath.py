
class MultipathConfigWriter:
    def __init__(self):
        self.blacklist_exceptions = []
        self.mpaths = []

    def addMultipathDevice(self, mpath):
        for parent in mpath.parents:
            self.blacklist_exceptions.append(parent.name)
        self.mpaths.append(mpath)

    def write(self):
        ret = ""
        ret += """\
# multipath.conf written by anaconda

blacklist {
        devnode "*"
}

blacklist_exceptions {
"""
        for device in self.blacklist_exceptions:
            ret += "\tdevnode \"^%s$\"\n" % (device,)
        ret += """\
}

multipaths {
"""
        for mpath in self.mpaths:
            ret += "\tmultipath {\n"
            for k,v in mpath.config.items():
                ret += "\t\t%s %s\n" % (k, v)
            ret += "\t}\n\n"
        ret += "}\n"

        return ret

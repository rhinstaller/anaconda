import _xkb
import tree
import string
import os

class XKB:
    def __init__ (self):
        self.rules = _xkb.list_rules ()                            

    def getRules (self):
        return self.rules

    def getModels (self):
        return self.rules[0]

    def getLayouts (self):
        return self.rules[1]

    def getVariants (self):
        return self.rules[2]

    def getOptions (self):
        keys = self.rules[3].keys (); keys.sort ()
        groups = ()
        for x in keys:
            groups = tree.merge (groups, string.split (x, ":"))
        return (groups, self.rules[3])

    def setRule (self, model, layout, variant, options):
	if model == None: model = ""
	if layout == None: layout = ""
	if variant == None: variant = ""
	if options == None: options = ""

	args = ()

	if (model):
            args = args + ("-model", model)
        if (layout):
            args = args + ("-layout", layout)
        if (variant):
            args = args + ("-variant", variant)

	path = ("/usr/X11R6/bin/setxkbmap",)
        child = os.fork ()
        if (child == 0):
            os.execv (path[0], path + args)

        pid, status = os.waitpid(child, 0)
        return

        # don't use any of our code, since it seems to corrupt
        # lots of memory
        return _xkb.set_rule (model, layout, variant, options)

    def getRulesBase (self):
        return _xkb.get_rulesbase ()

    def setMouseKeys (self, flag):
        return _xkb.set_mousekeys (flag)
    
    def getMouseKeys (self):
        return _xkb.get_mousekeys ()

if __name__ == "__main__":
    xkb = XKB()
    print xkb.getVariants()
        







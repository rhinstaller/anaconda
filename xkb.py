import _xkb
import tree
import string

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

        return _xkb.set_rule (model, layout, variant, options)

        
        
        
        

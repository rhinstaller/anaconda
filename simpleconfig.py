import string

class SimpleConfigFile:
    def __str__ (self):
        s = ""
        keys = self.info.keys ()
        keys.sort ()
        for key in keys:
            # FIXME - use proper escaping
            if type (self.info[key]) == type(""):
                s = s + key + "=\"" + self.info[key] + "\"\n"
        return s
            
    def __init__ (self):
        self.info = {}

    def set (self, *args):
        for (key, data) in args:
            self.info[string.upper (key)] = data

    def unset (self, *keys):
        for key in keys:
            key = string.upper (key)
            if self.info.has_key (key):
               del self.info[key] 

    def get (self, key):
        key = string.upper (key)
        if self.info.has_key (key):
            return self.info[key]
        else:
            return ""



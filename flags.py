# A lot of effort, but it only allows a limited set of flags to be referenced
class Flags:

    def __getattr__(self, attr):
	if self.__dict__['flags'].has_key(attr):
	    return self.__dict__['flags'][attr]

	raise AttributeError, attr

    def __setattr__(self, attr, val):
	if self.__dict__['flags'].has_key(attr):
	    self.__dict__['flags'][attr] = val
	else:
	    raise AttributeError, attr
	
    def __init__(self):
	self.__dict__['flags'] = {}
	self.__dict__['flags']['test'] = 0
	self.__dict__['flags']['expert'] = 0
	self.__dict__['flags']['serial'] = 0
	self.__dict__['flags']['setupFilesystems'] = 1


global flags
flags = Flags()

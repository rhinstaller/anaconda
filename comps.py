import rpm
from string import *

class Package:

    def __init__(self, header):
	self.h = header
	self.name = header[rpm.RPMTAG_NAME]

class Component:

    def __len__(self):
	return len(self.items)

    def __getitem__(self, key):
	return self.items[key]

    def addPackage(self, package):
	self.items.append(package)

    def addInclude(self, component):
	self.includes.append(component)

    def __init__(self, name, selected, hidden = 0):
	self.name = name
	self.hidden = hidden
	self.selected = selected
	self.items = []
	self.includes = []

class ComponentSet:
    def readCompsFile(self, arch, filename):
	file = open(filename, "r")
	lines = file.readlines()
	file.close()
	top = lines[0]
	lines = lines[1:]
	if (top != "2\n"):
	    raise TypeError, "comp file version 2 expected"
	
	comp = None
	self.comps = []
	self.compsDict = {}
	for l in lines:
	    l = l[:len(l) - 1]
	    if (not l): continue

	    if (find(l, ":") > -1):
		(archList, l) = split(l, ":", 1)
		while (l[0] == " "): l = l[1:]
		archList = split(archList)
		skip = 1
		for n in archList:
		    if (n == arch): 
			skip = 0
			break
		if (skip): continue

	    if (comp == None):
		(default, l) = split(l, None, 1)
		hidden = 0
		if (l[0:6] == "--hide"):
		    hidden = 1
		    (foo, l) = split(l, None, 1)
		    
		print "item is '%s'" % (l,)
		comp = Component(l, default, hidden)
	    elif (l == "end"):
		self.comps.append(comp)
		self.compsDict[comp.name] = comp
		comp = None
	    else:

		if (l[0] == "@"):
		    (at, l) = split(l, None, 1)
		    comp.addInclude(self.compsDict[l])
		else:
		    comp.addPackage(l)

    def __repr__(self):
	s = ""
	for n in self.comps:
	    s = s + "{ " + n.name + " [";
	    for include in n.includes:
		s = s + " @" + include.name
		
	    for package in n:
		s = s + " " + package
	    s = s + " ] } "
	    
	return s

    def __init__(self, arch, file):
	self.list = []
	self.readCompsFile(arch, file)

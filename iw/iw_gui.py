from translate import _

class InstallWindow:

    htmlTag = None
    windowTitle = None

    def __init__ (self,ics):
        self.ics = ics

	if self.htmlTag:
	    ics.readHTML (self.htmlTag)

	if self.windowTitle:
	    ics.setTitle (_(self.windowTitle))

    def getNext (self):
	return None

    def renderCallback(self):
	return None

    def getPrev (self):
	return None

    def getScreen (self):
        pass

    def getICS (self):
        return self.ics

    def fixUp (self):
        pass

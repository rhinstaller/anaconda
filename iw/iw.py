class InstallWindow:
    def __init__ (self,ics):
        self.ics = ics
	self.todo = ics.getToDo ()

    def getNext (self):
	return None

    def getPrev (self):
	return None

    def getScreen (self):
        pass

    def getICS (self):
        return self.ics

class ToDo:

    def addMount(self, device, location):
	self.mounts.append((device, location))

    def __init__(self):
	self.mounts = []
	pass

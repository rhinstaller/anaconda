import time

class Timer:

    def stop(self):
	if self.startedAt > -1:
	    self.total = self.total + (time.time() - self.startedAt)
	    self.startedAt = -1

    def start(self):
	if self.startedAt == -1:
	    self.startedAt = time.time()

    def elapsed(self):
	if self.startedAt == -1:
	    return self.total
	else:
	    return self.total + (time.time() - self.startedAt)

    def __init__(self, start = 1):
	self.total = 0
	self.startedAt = -1
	self.start()

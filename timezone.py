import iutil
from log import log

def bool(val):
    if val: return "true"
    return "false"

class Timezone:

    def writeKS(self, f):
	f.write("timezone")
	if self.utc:
	    f.write(" --utc")
	f.write(" %s\n" % self.tz)

    def write(self, instPath):
	fromFile = instPath + "/usr/share/zoneinfo/" + self.tz

	try:
	    iutil.copyFile(fromFile, instPath + "/etc/localtime")
	except OSError, (errno, msg):
	    log ("Error copying timezone (from %s): %s" % (fromFile, msg))

	f = open(instPath + "/etc/sysconfig/clock", "w")

	f.write('ZONE="%s"\n' % self.tz)
	f.write("UTC=%s\n" % bool(self.utc))
	f.write("ARC=%s\n" % bool(self.arc))

	f.close()

    def getTimezoneInfo(self):
	return (self.tz, self.utc, self.arc)

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.tz = timezone
	self.utc = asUtc
	self.arc = asArc

    def __init__(self):
	self.tz = "America/New_York"
	self.utc = 0
	self.arc = 0


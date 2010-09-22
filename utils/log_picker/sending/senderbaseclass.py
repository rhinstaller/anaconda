import datetime
from socket import gethostname


class SenderError(Exception):
    pass


class SenderBaseClass(object):
    
    def __init__(self, *args, **kwargs):
        pass
    
    def sendfile(self, filename, contenttype):
        raise NotImplementedError()
    
    def _get_description(self, prefix=""):
        try:
            hostname = gethostname()
        except:
            hostname = ""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        description = "%s (%s) %s" % (prefix, hostname, date_str)
        return description


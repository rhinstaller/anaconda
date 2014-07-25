import datetime
import socket

class SenderError(Exception):
    pass


class SenderBaseClass(object):
    
    def __init__(self, *args, **kwargs):
        pass
    
    def sendfile(self, filename, contenttype):
        raise NotImplementedError()
    
    def _get_description(self, prefix=""):
        try:
            hostname = socket.gethostname()
        except socket.herror:
            hostname = ""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        description = "%s (%s) %s" % (prefix, hostname, date_str)
        return description


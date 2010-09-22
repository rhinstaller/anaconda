import os
from log_picker.sending.senderbaseclass import SenderBaseClass
from log_picker.sending.senderbaseclass import SenderError
from report.plugins.bugzilla import filer
from report.plugins.bugzilla.filer import CommunicationError
from report.plugins.bugzilla.filer import LoginError


class BugzillaBaseClass(SenderBaseClass):

    _bz_address = ""
    _bz_xmlrpc = ""
    _description = ""
    
    def __init__(self, *args, **kwargs):
        SenderBaseClass.__init__(self, args, kwargs)
        self.bzfiler = None
        self.bug_id = None
        self.comment = None
    
    def connect_and_login(self, username, password):
        try:
            self.bzfiler = filer.BugzillaFiler(self._bz_xmlrpc, self._bz_address,
                                        filer.getVersion(), filer.getProduct())
            self.bzfiler.login(username, password)
        except (CommunicationError, LoginError) as e:
            raise SenderError("%s. Bad username or password?" % e)
        except (ValueError) as e:
            raise SenderError("%s" % e)
    
    def set_bug(self, bug_id):
        self.bug_id = bug_id
    
    def set_comment(self, comment):
        self.comment = comment
    
    def sendfile(self, filename, contenttype):
        description = self._get_description(self._description)

        dict_args = {'isprivate': False,
                     'filename': os.path.basename(filename),
                     'contenttype': contenttype}
        
        if self.comment:
            dict_args['comment'] = self.comment

        try:
            bug = self.bzfiler.getbug(self.bug_id)      
            bug.attachfile(filename, description, **dict_args)
        except (CommunicationError, ValueError) as e:
            raise SenderError(e)


class RedHatBugzilla(BugzillaBaseClass):

    _bz_address = "http://bugzilla.redhat.com"
    _bz_xmlrpc = "https://bugzilla.redhat.com/xmlrpc.cgi"
    _description = "LogPicker"
    
    def __init__(self, *args, **kwargs):
        BugzillaBaseClass.__init__(self, args, kwargs)


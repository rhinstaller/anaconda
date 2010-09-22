import xml.dom.minidom
from log_picker.sending.senderbaseclass import SenderBaseClass
from log_picker.sending.senderbaseclass import SenderError
from report.plugins.strata import send_report_to_existing_case
from report.plugins.strata import strata_client_strerror


class StrataSender(SenderBaseClass):
    
    _URL = "https://api.access.redhat.com/rs"
    _CERT_DATA = "INSECURE"
    
    def __init__(self, *args, **kwargs):
        SenderBaseClass.__init__(self, args, kwargs)
        self.username = None
        self.password = None
        self.case_number = None
    
    def set_login(self, username, password):
        self.username = username
        self.password = password
        
    def set_case_number(self, case_num):
        self.case_number = case_num
    
    def sendfile(self, filename, contenttype):
        response = send_report_to_existing_case(self._URL,
                                                self._CERT_DATA,
                                                self.username, 
                                                self.password,
                                                self.case_number, 
                                                filename)
        
        if not response:
            raise SenderError("Sending log to the Red Hat Ticket System fail" +\
                    " - %s" % strata_client_strerror())
        
        # Try parse response
        try:
            dom = xml.dom.minidom.parseString(response)
            mnode = dom.getElementsByTagName("response")[0]
            title = mnode.getElementsByTagName("title")[0].childNodes[0].data
            body = mnode.getElementsByTagName("body")[0].childNodes[0].data
        except Exception as e:
            raise SenderError("Sending log to the Red Hat Ticket System fail.")
        
        if title == "File Attachment Failed":
            if body.startswith("401 Unauthorized"):
                raise SenderError("Bad login or password.")
            elif body.startswith("Error : CASE_NOT_FOUND"):
                raise SenderError("Selected case doesn't exist.")
            else:
                raise SenderError("Sending log to the " +\
                            "Red Hat Ticket System fail - %s" % body.strip())


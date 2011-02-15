import os
import urlparse
import ftplib
from log_picker.sending.senderbaseclass import SenderBaseClass
from log_picker.sending.senderbaseclass import SenderError

# This class uses code from module report.plugins.scp

class FtpSender(SenderBaseClass):
    
    def __init__(self, *args, **kwargs):
        SenderBaseClass.__init__(self, args, kwargs)
        self.host = None
        self.username = None
        self.password = None

    def set_host(self, host):
        if not host.startswith('ftp://'):
            host = 'ftp://' + host
        self.host = host

    def set_login(self, username, password):
        self.username = username
        self.password = password

    def sendfile(self, filename, contenttype):       
        _, netloc, path, _, _, _ = urlparse.urlparse(self.host)
        if netloc.find(':') > 0:
            netloc, port = netloc.split(':')
        else:
            port = 21

        try:
            ftp = ftplib.FTP()
            ftp.connect(netloc, port)
            if self.username:
                ftp.login(self.username, self.password)
            else:
                ftp.login()
            ftp.cwd(path)
            ftp.set_pasv(True)
            ftp.storbinary('STOR %s' % os.path.basename(filename), \
                                                                file(filename))
            ftp.quit()
        except ftplib.all_errors as e:
            raise SenderError("FTP upload failed: %(error)s" % {'error':e})


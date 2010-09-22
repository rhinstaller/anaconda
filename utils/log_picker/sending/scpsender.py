import os
import subprocess
from log_picker.sending.senderbaseclass import SenderBaseClass
from log_picker.sending.senderbaseclass import SenderError


class ScpSender(SenderBaseClass):
    
    def __init__(self, *args, **kwargs):
        SenderBaseClass.__init__(self, args, kwargs)
        self.host = None
        self.port = None
        self.username = None
        self.path = "."


    def set_host(self, host):
        if host.find(":") != -1:
            (self.host, port) = host.split(":")
            try:
                self.port = int(port)
            except ValueError:
                self.port = None
        else:
            self.host = host
            
    
    def set_login(self, username):
        self.username = username
    
    
    def set_path(self, path):
        if path: self.path = path


    def sendfile(self, filename, contenttype):
        port_args = []
        if self.port:
            port_args = ["-P", self.port]

        target = "%s@%s:%s" % (self.username, self.host, self.path)

        command = ["scp", 
                    "-q",
                    "-oGSSAPIAuthentication=no",
                    "-oHostbasedAuthentication=no",
                    "-oPubkeyAuthentication=no",
                    "-oChallengeResponseAuthentication=no",
                    "-oPasswordAuthentication=yes",
                    "-oNumberOfPasswordPrompts=1",
                    "-oStrictHostKeyChecking=no",
                    "-oUserKnownHostsFile=/dev/null",
                    ] + port_args + [filename, target]

        p = subprocess.Popen(command, stdin=subprocess.PIPE) 
        p.communicate()

        if p.returncode:
            raise SenderError("Scp sending failed.\n" + \
                    "Possible causes: Bad hostname, bad username, "\
                    "bad password, host is down.")


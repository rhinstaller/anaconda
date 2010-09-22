import os
import smtplib
import email
import email.encoders
import email.mime.multipart
from log_picker.sending.senderbaseclass import SenderBaseClass
from log_picker.sending.senderbaseclass import SenderError


class EmailSender(SenderBaseClass):
   
    _description = "Email from LogPicker"
    
    def __init__(self, sendby, addresses, smtp_server, *args, **kwargs):
        """Send file by email.
        @sendby - Sender email address. (string)
        @addresses - List of destination email addresses. (list)
        @smtp_server - SMTP server address. (string)"""
        
        SenderBaseClass.__init__(self, args, kwargs)
        self.smtp_server = smtp_server
        self.sendby = sendby
        self.addresses = addresses
        self.comment = ""
    
    def set_comment(self, comment):
        self.comment = comment
    
    def sendfile(self, filename, contenttype):
        # Create email message
        msg = email.mime.multipart.MIMEMultipart()
        msg['Subject'] = self._get_description(self._description)
        msg['From'] = self.sendby
        msg['To'] = ', '.join(self.addresses)
        msg.preamble = 'This is a multi-part message in MIME format.'
        
        # Add message text
        msgtext = email.mime.base.MIMEBase("text", "plain")
        msgtext.set_payload(self.comment)
        msg.attach(msgtext)
        
        # Add message attachment
        cont_type = contenttype.split('/', 1)
        if len(cont_type) == 1:
            cont_type.append("")
        elif not cont_type:
            cont_type = ["application", "octet-stream"]
        
        attach_data = open(filename, 'rb').read()
        
        msgattach = email.mime.base.MIMEBase(cont_type[0], cont_type[1])
        msgattach.set_payload(attach_data)
        email.encoders.encode_base64(msgattach)
        msgattach.add_header('Content-Disposition', 'attachment', 
                filename=os.path.basename(filename))
        msg.attach(msgattach)
        
        # Send message
        try:
            s = smtplib.SMTP(self.smtp_server)
        except(smtplib.socket.gaierror, smtplib.SMTPServerDisconnected):
            raise SenderError("Email cannot be send. " +\
                                "Error while connecting to smtp server.")
        
        try:
            s.sendmail(self.sendby, self.addresses, msg.as_string())
        except(smtplib.SMTPRecipientsRefused) as e:
            raise SenderError("Email cannot be send. Wrong destination " +\
                                "email address?\nErr message: %s" % e)
        s.quit()


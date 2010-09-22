import os
import shutil
from log_picker.sending.senderbaseclass import SenderBaseClass
from log_picker.sending.senderbaseclass import SenderError


class LocalSender(SenderBaseClass):
    
    def __init__(self, *args, **kwargs):
        SenderBaseClass.__init__(self, args, kwargs)
        self.path = None

    def set_path(self, directory):
        self.path = directory
        
        if os.path.exists(self.path) and not os.path.isdir(self.path):
            raise SenderError('Cannot create "%s" directory. A file of '
                                    'the same name already exists.' % self.path)
    
        
    def sendfile(self, filename, contenttype):
        
        # Another check due possibility of race condition
        if os.path.exists(self.path):
            if not os.path.isdir(self.path):
                raise SenderError('Cannot create "%s" directory. A file of '
                                    'the same name already exists.' % self.path)
        else:
            try:
                os.makedirs(self.path)
            except Exception as e:
                raise SenderError('Cannot create "%s" directory: %s' % \
                                                                (self.path, e))
        try:
            shutil.copy(filename, self.path)
        except Exception as e:
            raise SenderError('Could not save "%s" to "%s": %s' % \
                                (os.path.basename(filename), self.path, e))


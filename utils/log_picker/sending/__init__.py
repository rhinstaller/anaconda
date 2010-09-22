from log_picker.sending.senderbaseclass import SenderError

RHBZ = 0   # RedHat Bugzilla
EMAIL = 1  # Email
STRATA = 2 # Red Hat ticketing system
SCP = 3    # Scp
FTP = 4    # Ftp
LOCAL = 5  # Local

NOT_AVAILABLE = []


try:
    from log_picker.sending.bugzillasender import RedHatBugzilla
except (ImportError):
    NOT_AVAILABLE.append(RHBZ)

try:
    from log_picker.sending.emailsender import EmailSender
except (ImportError):
    NOT_AVAILABLE.append(EMAIL)

try:
    from log_picker.sending.stratasender import StrataSender
except (ImportError):
    NOT_AVAILABLE.append(STRATA)
    
try:
    from log_picker.sending.scpsender import ScpSender
except (ImportError):
    NOT_AVAILABLE.append(SCP)

try:
    from log_picker.sending.ftpsender import FtpSender
except (ImportError):
    NOT_AVAILABLE.append(FTP)

try:
    from log_picker.sending.localsender import LocalSender
except (ImportError):
    NOT_AVAILABLE.append(LOCAL)


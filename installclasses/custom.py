from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from translate import N_
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):

    name = N_("Custom System")
    pixmap = "custom.png"
    
    sortPriority = 10000



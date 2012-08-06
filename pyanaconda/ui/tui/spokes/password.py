from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget
import getpass

class PasswordSpoke(NormalTUISpoke):
    title = "Set root password"
    category = "password"

    def __init__(self, app, ksdata, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, ksdata, storage, payload, instclass)
        self._password = None

    @property
    def completed(self):
        return self._password is not None

    @property
    def status(self):
        if self._password is None:
            return "Password is not set."
        else:
            return "Password is set."

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)

        self._window += [TextWidget("Please select new root password. You will have to type it twice."), ""]

        return True

    def prompt(self, args = None):
        """Overriden prompt as password typing is special."""
        p1 = getpass.getpass("Password: ")
        p2 = getpass.getpass("Password (confirm): ")

        if p1 != p2:
            print "Passwords do not match!"
        else:
            self._password = p1
            self.apply()

        self.close()
        #return None

    def apply(self):
        self.data.rootpw.password = self._password
        self.data.rootpw.isCrypted = False

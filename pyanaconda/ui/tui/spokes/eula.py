import logging

from pyanaconda.ui.tui.spokes import NormalTUISpoke
from simpleline.render.widgets import TextWidget, CheckboxWidget
from simpleline.render.containers import ListRowContainer
from simpleline.render.screen import UIScreen, InputState
from simpleline.render.screen_handler import ScreenHandler
from pyanaconda.ui.common import FirstbootOnlySpokeMixIn
from pyanaconda.core import eula
from pyanaconda.ui.categories.eula import LicensingCategory
from pyanaconda.core.i18n import _, N_
from pykickstart.constants import FIRSTBOOT_RECONFIG

log = logging.getLogger("initial-setup")

__all__ = ["EULASpoke"]


class EULASpoke(FirstbootOnlySpokeMixIn, NormalTUISpoke):
    """The EULA spoke providing ways to read the license and agree/disagree with it."""

    category = LicensingCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "license-information"

    def __init__(self, *args, **kwargs):
        NormalTUISpoke.__init__(self, *args, **kwargs)
        self.title = _("License information")
        self._container = None

    def initialize(self):
        NormalTUISpoke.initialize(self)

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        self._container = ListRowContainer(1)

        log.debug("license found")
        # make the options aligned to the same column (the checkbox has the
        # '[ ]' prepended)
        self._container.add(TextWidget("%s\n" % _("Read the License Agreement")),
                            self._show_license_screen_callback)

        self._container.add(CheckboxWidget(title=_("I accept the license agreement"),
                                           completed=self.data.eula.agreed),
                            self._license_accepted_callback)
        self.window.add_with_separator(self._container)

    @property
    def completed(self):
        # Either there is no EULA available, or user agrees/disagrees with it.
        return self.data.eula.agreed

    @property
    def mandatory(self):
        # This spoke is always mandatory.
        return True

    @property
    def status(self):
        return _("License accepted") if self.data.eula.agreed else _("License not accepted")

    @classmethod
    def should_run(cls, environment, data):
        if eula.eula_available():
            # don't run if we are in initial-setup in reconfig mode and the EULA has already been accepted
            if FirstbootOnlySpokeMixIn.should_run(environment, data) and data and data.firstboot.firstboot == FIRSTBOOT_RECONFIG and data.eula.agreed:
                log.debug("not running license spoke: reconfig mode & license already accepted")
                return False
            return True
        return False

    def apply(self):
        # nothing needed here, the agreed field is changed in the input method
        pass

    def input(self, args, key):
        if not self._container.process_user_input(key):
            return key

        return InputState.PROCESSED

    @staticmethod
    def _show_license_screen_callback(data):
        # show license
        log.debug("showing the license")
        eula_screen = LicenseScreen()
        ScreenHandler.push_screen(eula_screen)

    def _license_accepted_callback(self, data):
        # toggle EULA agreed checkbox by changing ksdata
        log.debug("license accepted state changed to: %s", self.data.eula.agreed)
        self.data.eula.agreed = not self.data.eula.agreed
        self.redraw()


class LicenseScreen(UIScreen):
    """Screen showing the License without any input from user requested."""

    def __init__(self):
        super().__init__()

        self._license_file = eula.get_license_file_name()

    def refresh(self, args=None):
        super().refresh(args)

        # read the license file and make it one long string so that it can be
        # processed by the TextWidget to fit in the screen in a best possible
        # way
        log.debug("reading the license file")
        with open(self._license_file, 'r') as f:
            license_text = f.read()

        self.window.add_with_separator(TextWidget(license_text))

    def input(self, args, key):
        """ Handle user input. """
        return InputState.PROCESSED_AND_CLOSE

    def prompt(self, args=None):
        # we don't want to prompt user, just close the screen
        self.close()
        return None

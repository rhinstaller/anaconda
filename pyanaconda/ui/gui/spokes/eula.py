import logging

from pyanaconda.ui.common import FirstbootOnlySpokeMixIn
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.core.i18n import _, CN_
from pyanaconda.core import eula
from pyanaconda.ui.categories.eula import LicensingCategory
from pyanaconda.anaconda_loggers import get_module_logger
from pykickstart.constants import FIRSTBOOT_RECONFIG

log = get_module_logger(__name__)
__all__ = ["EULASpoke"]


class EULASpoke(FirstbootOnlySpokeMixIn, NormalSpoke):
    """The EULA spoke"""

    builderObjects = ["eulaBuffer", "eulaWindow"]
    mainWidgetName = "eulaWindow"
    uiFile = "spokes/eula.glade"
    icon = "application-certificate-symbolic"
    title = CN_("GUI|Spoke", "_License Information")
    category = LicensingCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "license-information"

    def initialize(self):
        log.debug("initializing the EULA spoke")
        NormalSpoke.initialize(self)

        self._have_eula = True
        self._eula_buffer = self.builder.get_object("eulaBuffer")
        self._agree_check_button = self.builder.get_object("agreeCheckButton")
        self._agree_label = self._agree_check_button.get_child()
        self._agree_text = self._agree_label.get_text()

        log.debug("looking for the license file")
        license_file = eula.get_license_file_name()
        if not license_file:
            log.error("no license found")
            self._have_eula = False
            self._eula_buffer.set_text(_("No license found"))
            return

        # if there is "eula <...>" in kickstart, use its value
        if self.data.eula.agreed is not None:
            self._agree_check_button.set_active(self.data.eula.agreed)

        self._eula_buffer.set_text("")
        itr = self._eula_buffer.get_iter_at_offset(0)
        log.debug("opening the license file")
        with open(license_file, "r") as fobj:
            # insert the first line without prefixing with space
            try:
                first_line = next(fobj)
            except StopIteration:
                # nothing in the file
                return
            self._eula_buffer.insert(itr, first_line.strip())

            # EULA file may be preformatted for the console, we want to let Gtk
            # format it (blank lines should be preserved)
            for line in fobj:
                stripped_line = line.strip()
                if stripped_line:
                    self._eula_buffer.insert(itr, " " + stripped_line)
                else:
                    self._eula_buffer.insert(itr, "\n\n")

    def refresh(self):
        self._agree_check_button.set_sensitive(self._have_eula)
        self._agree_check_button.set_active(self.data.eula.agreed)

    def apply(self):
        self.data.eula.agreed = self._agree_check_button.get_active()

    @property
    def completed(self):
        return not self._have_eula or self.data.eula.agreed

    @property
    def status(self):
        if not self._have_eula:
            return _("No license found")

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

    def on_check_button_toggled(self, *args):
        if self._agree_check_button.get_active():
            log.debug("license is now accepted")
            self._agree_label.set_markup("<b>%s</b>" % self._agree_text)
        else:
            log.debug("license no longer accepted")
            self._agree_label.set_markup(self._agree_text)

from pyanaconda import ui
from pyanaconda.ui import common
import simpleline as tui
from hubs.summary import SummaryHub
from spokes import StandaloneSpoke

class ErrorDialog(tui.UIScreen):
    """Dialog screen for reporting errors to user."""

    title = u"Error"

    def __init__(self, app, message):
        """
        :param app: the running application reference
        :type app: instance of App class

        :param message: the message to show to the user
        :type message: unicode
        """

        tui.UIScreen.__init__(self, app)
        self._message = message

    def refresh(self, args = None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window.append(tui.CenterWidget(text))

    def prompt(self):
        return u"Press enter to exit."

    def input(self, key):
        """This dialog is closed by any input."""
        self.close()

class YesNoDialog(tui.UIScreen):
    """Dialog screen for Yes - No questions."""

    title = u"Question"

    def __init__(self, app, message):
        """
        :param app: the running application reference
        :type app: instance of App class

        :param message: the message to show to the user
        :type message: unicode
        """

        tui.UIScreen.__init__(self, app)
        self._message = message
        self._response = None

    def refresh(self, args = None):
        tui.UIScreen.refresh(self, args)
        text = tui.TextWidget(self._message)
        self._window.append(tui.CenterWidget(text))
        self._window.append(u"")
        return True

    def prompt(self):
        return u"Please respond 'yes' or 'no': "

    def input(self, key):
        if key == "yes":
            self._response = True
            self.close()
            return None

        elif key == "no":
            self._response = False
            self.close()
            return None

        else:
            return False

    @property
    def answer(self):
        """The response can be True (yes), False (no) or None (no response)."""
        return self._response

class TextUserInterface(ui.UserInterface):
    """This is the main class for Text user interface."""

    def __init__(self, storage, payload, instclass):
        """
        For detailed description of the arguments see
        the parent class.

        :param storage: storage backend reference
        :type storage: instance of pyanaconda.Storage

        :param payload: payload (usually yum) reference
        :type payload: instance of payload handler

        :param instclass: install class reference
        :type instclass: instance of install class
        """

        ui.UserInterface.__init__(self, storage, payload, instclass)
        self._app = None

    def setup(self, data):
        """Construct all the objects required to implement this interface.
           This method must be provided by all subclasses.
        """
        self._app = tui.App(u"Anaconda", yes_or_no_question = YesNoDialog)
        self._hubs = [SummaryHub]

        # First, grab a list of all the standalone spokes.
        path = os.path.join(os.path.dirname(__file__), "spokes")
        actionClasses = self.getActionClasses("pyanaconda.ui.tui.spokes.%s", path, self._hubs, StandaloneSpoke)

        for klass in actionClasses:
            obj = klass(self._app, data, self.storage, self.payload, self.instclass)

            # If we are doing a kickstart install, some standalone spokes
            # could already be filled out.  In taht case, we do not want
            # to display them.
            if isinstance(obj, StandaloneSpoke) and obj.completed:
                del(obj)
                continue

            self._app.schedule_window(obj)

    def run(self):
        """Run the interface.  This should do little more than just pass
           through to something else's run method, but is provided here in
           case more is needed.  This method must be provided by all subclasses.
        """
        self._app.run()

    ###
    ### MESSAGE HANDLING METHODS
    ###
    def showError(self, message):
        """Display an error dialog with the given message.  After this dialog
           is displayed, anaconda will quit.  There is no return value.  This
           method must be implemented by all UserInterface subclasses.

           In the code, this method should be used sparingly and only for
           critical errors that anaconda cannot figure out how to recover from.
        """
        error_window = ErrorDialog(self._app, message)
        self._app.switch_window(error_window)

    def showYesNoQuestion(self, message):
        """Display a dialog with the given message that presents the user a yes
           or no choice.  This method returns True if the yes choice is selected,
           and False if the no choice is selected.  From here, anaconda can
           figure out what to do next.  This method must be implemented by all
           UserInterface subclasses.

           In the code, this method should be used sparingly and only for those
           times where anaconda cannot make a reasonable decision.  We don't
           want to overwhelm the user with choices.
        """
        question_window = YesNoDialog(self._app, message)
        self._app.switch_window_modal(question_window)
        return question_window.answer

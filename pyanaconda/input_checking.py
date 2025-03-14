#
# input_checking.py : input & password/passphrase input checking
#
# Copyright (C) 2013, 2017  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import pwquality

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants, regexes, users
from pyanaconda.core.i18n import _
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.constants.services import RUNTIME
from pyanaconda.modules.common.structures.policy import PasswordPolicy

log = get_module_logger(__name__)


def get_policy(policy_name) -> PasswordPolicy:
    """Get the password policy data.

    :param policy_name: a name of the policy
    :return: a password policy data
    """
    proxy = RUNTIME.get_proxy(USER_INTERFACE)
    policies = PasswordPolicy.from_structure_dict(proxy.PasswordPolicies)

    if policy_name in policies:
        return policies[policy_name]

    return PasswordPolicy.from_defaults(policy_name)


class PwqualitySettingsCache:
    """Cache for libpwquality settings used for password validation.

    Libpwquality settings instantiation is probably not exactly cheap
    and we might need the settings for checking every password (even when
    it is being typed by the user) so it makes sense to cache the objects
    for reuse. As there might be multiple active policies for different
    passwords we need to be able to cache multiple policies based on
    minimum password length, as we don't input anything else to libpwquality
    than minimum password length and the password itself.
    """
    def __init__(self):
        self._pwq_settings = {}

    def get_settings_by_minlen(self, minlen):
        settings = self._pwq_settings.get(minlen)
        if settings is None:
            settings = pwquality.PWQSettings()  # pylint: disable=c-extension-no-member
            settings.read_config()
            settings.minlen = minlen
            self._pwq_settings[minlen] = settings
        return settings


pwquality_settings_cache = PwqualitySettingsCache()


class PasswordCheckRequest:
    """A wrapper for a password check request.

    This in general means the password to be checked as well as its validation criteria
    such as minimum length, if it can be empty, etc.
    """

    def __init__(self):
        self._password = ""
        self._password_confirmation = ""
        self._policy = None
        self._pwquality_settings = None
        self._username = "root"
        self._fullname = ""
        self._secret_type = constants.SecretType.PASSWORD

    @property
    def password(self):
        """Password string to be checked.

        :returns: password string for the check
        :rtype: str
        """
        return self._password

    @password.setter
    def password(self, new_password):
        self._password = new_password

    @property
    def password_confirmation(self):
        """Content of the password confirmation field.

        :returns: password confirmation string
        :rtype: str
        """
        return self._password_confirmation

    @password_confirmation.setter
    def password_confirmation(self, new_password_confirmation):
        self._password_confirmation = new_password_confirmation

    @property
    def policy(self):
        """Password quality policy.

        :returns: password quality policy
        """
        return self._policy

    @policy.setter
    def policy(self, new_policy):
        self._policy = new_policy

    @property
    def pwquality_settings(self):
        """Settings for libpwquality (if any).

        :returns: libpwquality settings
        :rtype: pwquality settings object or None
        """
        if not self._pwquality_settings:
            # pylint: disable=c-extension-no-member
            self._pwquality_settings = pwquality_settings_cache.get_settings_by_minlen(
                self.policy.min_length
            )
        return self._pwquality_settings

    @property
    def username(self):
        """The username for which the password is being set.

        If no username is provided, "root" will be used.
        Use username=None to disable the username check.

        :returns: username corresponding to the password
        :rtype: str or None
        """
        return self._username

    @username.setter
    def username(self, new_username):
        self._username = new_username

    @property
    def fullname(self):
        """The full name of the user for which the password is being set.

        If no full name is provided, "root" will be used.

        :returns: full user name corresponding to the password
        :rtype: str or None
        """
        return self._fullname

    @fullname.setter
    def fullname(self, new_fullname):
        self._fullname = new_fullname

    @property
    def secret_type(self):
        """Type of secret that is being checked.

        At the moment is either a password or a passphrase and this property decides how it will be
        called in error and status messages.

        :returns: secret type
        :rtype: Enum
        """
        return self._secret_type

    @secret_type.setter
    def secret_type(self, new_type):
        """Set type of secret being checked.

        :param Enum new_type: new secret type
        """
        # Prevent uknown/unsuported secret type from being set, so that
        # this does no blow up later on once we try to access the status/error message
        # corresponding to the secret type.
        if new_type not in constants.SecretType:
            raise RuntimeError("Unknown secret type: {}".format(new_type))
        self._secret_type = new_type


class CheckResult:
    """Result of an input check."""

    def __init__(self):
        self._success = False
        self._error_message = ""
        self.error_message_changed = Signal()

    @property
    def success(self):
        return self._success

    @success.setter
    def success(self, value):
        self._success = value

    @property
    def error_message(self):
        """Optional error message describing why the input is not valid.

        :returns: why the input is bad (provided it is bad) or None
        :rtype: str or None
        """
        return self._error_message

    @error_message.setter
    def error_message(self, new_error_message):
        self._error_message = new_error_message
        self.error_message_changed.emit(new_error_message)


class PasswordValidityCheckResult(CheckResult):
    """A wrapper for results for a password check."""

    def __init__(self):
        super().__init__()
        self._password_score = 0
        self.password_score_changed = Signal()
        self._status_text = ""
        self.status_text_changed = Signal()
        self._password_quality = 0
        self.password_quality_changed = Signal()
        self._length_ok = False
        self.length_ok_changed = Signal()

    @property
    def password_score(self):
        """A high-level integer score indicating password quality.

        Goes from 0 (invalid password) to 4 (valid & very strong password).
        Mainly used to drive the password quality indicator in the GUI.
        """
        return self._password_score

    @password_score.setter
    def password_score(self, new_score):
        self._password_score = new_score
        self.password_score_changed.emit(new_score)

    @property
    def status_text(self):
        """A short overall status message describing the password.

        Generally something like "Good.", "Too short.", "Empty.", etc.

        :rtype: short status message
        :rtype: str
        """
        return self._status_text

    @status_text.setter
    def status_text(self, new_status_text):
        self._status_text = new_status_text
        self.status_text_changed.emit(new_status_text)

    @property
    def password_quality(self):
        """More fine grained integer indicator describing password strength.

        This basically exports the quality score assigned by libpwquality to the password,
        which goes from 0 (unacceptable password) to 100 (strong password).

        Note of caution though about using the password quality value - it is intended
        mainly for on-line password strength hints, not for long-term stability,
        even just because password dictionary updates and other peculiarities of password
        strength judging.

        :returns: password quality value as reported by libpwquality
        :rtype: int
        """
        return self._password_quality

    @password_quality.setter
    def password_quality(self, value):
        self._password_quality = value
        self.password_quality_changed.emit(value)

    @property
    def length_ok(self):
        """Reports if the password is long enough.

        :returns: if the password is long enough
        :rtype: bool
        """
        return self._length_ok

    @length_ok.setter
    def length_ok(self, value):
        self._length_ok = value
        self.length_ok_changed.emit(value)


class InputCheck:
    """Input checking base class."""

    def __init__(self):
        self._result = CheckResult()
        self._skip = False

    @property
    def result(self):
        return self._result

    @property
    def skip(self):
        """A flag hinting if this check should be skipped."""
        return self._skip

    @skip.setter
    def skip(self, value):
        # Checks flagged as skipped are
        # considered successful.
        # Otherwise old state will linger even if the
        # check is skipped during checking runs.
        if value:
            self.result.error_message = ""
            self.result.success = True
        self._skip = value

    def run(self, check_request):
        """Run the check.

        :param check_request: arbitrary input data to be processed

        Subclasses need to always implement this.
        """
        raise NotImplementedError


class PasswordValidityCheck(InputCheck):
    """Check the validity and quality of a password."""

    def __init__(self):
        super().__init__()
        self._result = PasswordValidityCheckResult()

    def run(self, check_request):
        """Check the validity and quality of a password.

           This is how password quality checking works:
           - starts with a password and an optional parameters
           - will report if this password can be used at all (score >0)
           - will report how strong the password approximately is on a scale of 1-100
           - if the password is unusable it will be reported why

           This function uses libpwquality to check the password strength.
           Pwquality will raise a PWQError on a weak password but this function does
           not pass that forward.

           If the password fails the PWQSettings conditions, the score will be set to 0
           and the resulting error message will contain the reason why the password is bad.

           :param check_request: a password check request wrapper
           :type check_request: a PasswordCheckRequest instance
           :returns: a password check result wrapper
           :rtype: a PasswordCheckResult instance
        """

        length_ok = False
        error_message = ""
        pw_quality = 0
        try:
            # lets run the password through libpwquality
            pw_quality = check_request.pwquality_settings.check(check_request.password, None, check_request.username)
        # pylint: disable=c-extension-no-member
        except pwquality.PWQError as e:
            # Leave valid alone here: the password is weak but can still
            # be accepted.
            # PWQError values are built as a tuple of (int, str)
            error_message = e.args[1]

        if check_request.policy.allow_empty and not check_request.password:
            # if we are OK with empty passwords, then empty passwords are also fine length wise
            length_ok = True
        else:
            length_ok = len(check_request.password) >= check_request.policy.min_length

        if not check_request.password:
            if check_request.policy.allow_empty:
                pw_score = 1
            else:
                pw_score = 0
            status_text = _(constants.SecretStatus.EMPTY.value)
        elif not length_ok:
            pw_score = 0
            status_text = _(constants.SecretStatus.TOO_SHORT.value)
            # If the password is too short replace the libpwquality error
            # message with a generic "password is too short" message.
            # This is because the error messages returned by libpwquality
            # for short passwords don't make much sense.
            error_message = _(constants.SECRET_TOO_SHORT[check_request.secret_type])
        elif error_message:
            pw_score = 1
            status_text = _(constants.SecretStatus.WEAK.value)
        elif pw_quality < 30:
            pw_score = 2
            status_text = _(constants.SecretStatus.FAIR.value)
        elif pw_quality < 70:
            pw_score = 3
            status_text = _(constants.SecretStatus.GOOD.value)
        else:
            pw_score = 4
            status_text = _(constants.SecretStatus.STRONG.value)

        # the policy influences the overall success of the check
        # - score 0 & strict == True -> success = False
        # - score 0 & strict == False -> success = True
        success = not error_message

        # set the result now so that the *_changed signals fire only once the check is done
        self.result.success = success  # pylint: disable=attribute-defined-outside-init
        self.result.password_score = pw_score  # pylint: disable=attribute-defined-outside-init
        self.result.status_text = status_text  # pylint: disable=attribute-defined-outside-init
        self.result.password_quality = pw_quality  # pylint: disable=attribute-defined-outside-init
        self.result.error_message = error_message  # pylint: disable=attribute-defined-outside-init
        self.result.length_ok = length_ok  # pylint: disable=attribute-defined-outside-init


class PasswordFIPSCheck(InputCheck):
    """Check if the password is valid under FIPS, if applicable."""

    def run(self, check_request):
        self.result.success = True
        self.result.error_message = ""

        if not kernel_arguments.is_enabled("fips"):
            return

        if len(check_request.password) >= constants.FIPS_PASSPHRASE_MIN_LENGTH:
            return

        self.result.success = False
        self.result.error_message = _(
            "In FIPS mode, the passphrase must be at least {} letters long."
        ).format(constants.FIPS_PASSPHRASE_MIN_LENGTH)


class PasswordConfirmationCheck(InputCheck):
    """Check if the password & password confirmation match."""

    def __init__(self):
        super().__init__()
        self._success_if_confirmation_empty = False

    @property
    def success_if_confirmation_empty(self):
        """Enables success-if-confirmation-empty mode.

        This property can be used to tell the check to report success if the confirmation filed is empty,
        which is a paradigm used by Anaconda uses for two things:
        - to make it possible for users to exit without setting a valid password
        - to make it possible to exit the spoke if only the password is set
          but confirmation is empty
        """
        return self._success_if_confirmation_empty

    @success_if_confirmation_empty.setter
    def success_if_confirmation_empty(self, value):
        self._success_if_confirmation_empty = value

    def run(self, check_request):
        """If the user has entered confirmation data, check whether it matches the password."""
        if self.success_if_confirmation_empty and not check_request.password_confirmation:
            self.result.error_message = ""
            self.result.success = True
        elif check_request.password != check_request.password_confirmation:
            self.result.error_message = _(constants.SECRET_CONFIRM_ERROR_GUI[check_request.secret_type])
            self.result.success = False
        else:
            self.result.error_message = ""
            self.result.success = True


class PasswordASCIICheck(InputCheck):
    """Check if the password contains non-ASCII characters.

    Non-ASCII characters might be hard to type in the console and in the LUKS volume unlocking
    screen, so check if the password contains them so we can warn the user.
    """

    def run(self, check_request):
        """Fail if the password contains non-ASCII characters."""
        has_non_ASCII = any(char not in constants.PW_ASCII_CHARS for char in check_request.password)
        if check_request.password and has_non_ASCII:
            self.result.error_message = _(constants.SECRET_ASCII[check_request.secret_type])
            self.result.success = False
        else:
            self.result.error_message = ""
            self.result.success = True


class PasswordEmptyCheck(InputCheck):
    """Check if the password is set."""

    def run(self, check_request):
        """Check whether a password has been specified at all."""
        if check_request.password:
            # password set is always success
            self.result.error_message = ""
            self.result.success = True
        else:
            # otherwise empty password is an error
            self.result.error_message = _(constants.SECRET_EMPTY_ERROR[check_request.secret_type])
            self.result.success = False


class UsernameCheck(InputCheck):
    """Check if the username is valid."""

    def __init__(self):
        super().__init__()
        self._success_if_username_empty = False

    @property
    def success_if_username_empty(self):
        """Should empty username be considered a success ?"""
        return self._success_if_username_empty

    @success_if_username_empty.setter
    def success_if_username_empty(self, value):
        self._success_if_username_empty = value

    def run(self, check_request):
        """Check if the username is valid."""
        # in some cases an empty username is also considered valid,
        # so that the user can exit the User spoke without filling it in
        if self.success_if_username_empty and not check_request.username:
            self.result.error_message = ""
            self.result.success = True
        else:
            success, error_message = users.check_username(check_request.username)
            self.result.error_message = error_message
            self.result.success = success


class FullnameCheck(InputCheck):
    """Check if the full user name is valid.

    Most importantly the full user name cannot contain colons.
    """

    def run(self, check_request):
        """Check if the full user name is valid."""
        if regexes.GECOS_VALID.match(check_request.fullname):
            self.result.error_message = ""
            self.result.success = True
        else:
            self.result.error_message = _("Full name cannot contain colon characters")
            self.result.success = False


class InputField:
    """An input field containing data to be checked.

    The input field can have an initial value that can be
    monitored for change via signals.
    """

    def __init__(self, initial_content):
        self._initial_content = initial_content
        self._content = initial_content
        self.changed = Signal()
        self._initial_change_signal_fired = False
        self.changed_from_initial_state = Signal()

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, new_content):
        old_content = self._content
        self._content = new_content
        # check if the input changed from the initial state
        if old_content != new_content:
            self.changed.emit()
            # also fire the changed-from-initial-state signal if required
            if not self._initial_change_signal_fired and new_content != self._initial_content:
                self.changed_from_initial_state.emit()
                self._initial_change_signal_fired = True


class PasswordChecker:
    """Run multiple password and input checks in a given order and report the results.

    All added checks (in insertion order) will be run and results returned as error message
    and success value (True/False). If any check fails success will be False and the
    error message of the first check to fail will be returned.

    It's also possible to mark individual checks to be skipped by setting their skip property to True.
    Such check will be skipped during the checking run.
    """

    def __init__(self, initial_password_content, initial_password_confirmation_content,
                 policy_name):
        self._password = InputField(initial_password_content)
        self._password_confirmation = InputField(initial_password_confirmation_content)
        self._checks = []
        self._success = False
        self._error_message = ""
        self._failed_checks = []
        self._policy_name = policy_name
        self._username = None
        self._fullname = ""
        self._secret_type = constants.SecretType.PASSWORD
        # connect to the password field signals
        self.password.changed.connect(self.run_checks)
        self.password_confirmation.changed.connect(self.run_checks)

        # signals
        self.checks_done = Signal()

    @property
    def password(self):
        """Main password field."""
        return self._password

    @property
    def password_confirmation(self):
        """Password confirmation field."""
        return self._password_confirmation

    @property
    def checks(self):
        return self._checks

    @property
    def success(self):
        return self._success

    @property
    def error_message(self):
        return self._error_message

    @property
    def failed_checks(self):
        """List of checks failed during the last checking run.

        If no checks have failed the list will be empty.

        :returns: list of failed checks (if any)
        :rtype: list
        """
        return self._failed_checks

    @property
    def policy(self):
        return get_policy(self._policy_name)

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, new_username):
        self._username = new_username

    @property
    def fullname(self):
        """The full name of the user for which the password is being set.

        If no full name is provided, "root" will be used.

        :returns: full user name corresponding to the password
        :rtype: str or None
        """
        return self._fullname

    @fullname.setter
    def fullname(self, new_fullname):
        self._fullname = new_fullname

    @property
    def secret_type(self):
        """Type of secret that is being checked.

        At the moment is either a password or a passphrase and this property decides how it will be
        called in error and status messages.

        :returns: secret type
        :rtype: Enum
        """
        return self._secret_type

    @secret_type.setter
    def secret_type(self, new_type):
        """Set type of secret being checked.

        :param Enum new_type: new secret type
        """
        # Prevent uknown/unsuported secret type from being set, so that
        # this does no blow up later on once we try to access the status/error message
        # corresponding to the secret type.
        if new_type not in constants.SecretType:
            raise RuntimeError("Unknown secret type: {}".format(new_type))
        self._secret_type = new_type

    def add_check(self, check_instance):
        """Add check instance to list of checks."""
        self._checks.append(check_instance)

    def run_checks(self):
        # first we need to prepare a check request instance
        check_request = PasswordCheckRequest()
        check_request.password = self.password.content
        check_request.password_confirmation = self.password_confirmation.content
        check_request.policy = self.policy
        check_request.username = self.username
        check_request.fullname = self.fullname
        check_request.secret_type = self.secret_type

        # reset the list of failed checks
        self._failed_checks = []

        error_message = ""
        for check in self.checks:
            if not check.skip:
                check.run(check_request)
                if not check.result.success:
                    if not self.failed_checks:
                        # a check failed:
                        # - remember that & it's error message
                        # - run other checks as well and ignore their error messages (if any)
                        # - fail the overall check run (success = False)
                        error_message = check.result.error_message
                    self._failed_checks.append(check)
        if self.failed_checks:
            self._error_message = error_message
            self._success = False
        else:
            self._success = True
            self._error_message = ""
        # trigger the success changed signal
        self.checks_done.emit(self._error_message)

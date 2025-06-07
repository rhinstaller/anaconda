#
# argument_parsing.py: option parsing for anaconda (CLI and boot args)
#
# Copyright (C) 2012 Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

DESCRIPTION = "Anaconda is the installation program used by Fedora, " \
              "Red Hat Enterprise Linux and some other distributions."

import itertools
import os
from argparse import (
    SUPPRESS,
    Action,
    ArgumentError,
    ArgumentParser,
    HelpFormatter,
    Namespace,
)

from blivet.arch import is_s390

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import VIRTIO_PORT, X_TIMEOUT, DisplayModes
from pyanaconda.core.kernel import KernelArguments

log = get_module_logger(__name__)

# Help text formatting constants

LEFT_PADDING = 8  # the help text will start after 8 spaces
RIGHT_PADDING = 8  # there will be 8 spaces left on the right
DEFAULT_HELP_WIDTH = 80


def get_help_width():
    """
    Try to detect the terminal window width size and use it to
    compute optimal help text width. If it can't be detected
    a default values is returned.

    :returns: optimal help text width in number of characters
    :rtype: int
    """
    # don't do terminal size detection on s390, it is not supported
    # by its arcane TTY system and only results in cryptic error messages
    # ending on the standard output
    if is_s390():
        return DEFAULT_HELP_WIDTH

    try:
        columns = os.get_terminal_size().columns
    except OSError as e:
        log.info("Unable to determine terminal width: %s", e)
        print("terminal size detection failed, using default width")
        return DEFAULT_HELP_WIDTH

    log.debug("detected window size of %s", columns)

    # apply the right padding
    columns = columns - RIGHT_PADDING
    if columns > 0:
        help_width = columns
    else:
        help_width = DEFAULT_HELP_WIDTH

    return help_width


class AnacondaArgumentParser(ArgumentParser):
    """
    Subclass of ArgumentParser that also examines boot arguments.
    """

    def __init__(self, *args, **kwargs):
        """
        If the "bootarg_prefix" keyword argument is set, it's assumed that all
        bootargs will start with that prefix.

        "require_prefix" is a bool:
            False: accept the argument with or without the prefix.
            True: ignore the argument without the prefix. (default)
        """
        help_width = get_help_width()
        self._boot_arg = {}
        self.bootarg_prefix = kwargs.pop("bootarg_prefix", "")
        self.require_prefix = kwargs.pop("require_prefix", True)

        # List of boot options which are correct with and without the inst. prefix
        # Please add here options which are processed by us but also by someone
        # else during the boot.
        # NOTE: Adding this to add_argument() directly could be problematic because just specific
        # long option variants could be allowed from multiple, so it would have to be list which
        # somehow kills the benefit.
        self._require_prefix_ignore_list = ["proxy"]
        ArgumentParser.__init__(self, description=DESCRIPTION,
                                formatter_class=lambda prog: HelpFormatter(
                                    prog, max_help_position=LEFT_PADDING, width=help_width),
                                *args, **kwargs)

    def add_argument(self, *args, **kwargs):
        """
        Add a new option - like ArgumentParser.add_argument.

        The long options will be added to the list of boot args, unless
        the keyword argument 'bootarg' is set to False.

        Positional arguments that don't start with '-' are considered extra
        boot args to look for.

        NOTE: conflict_handler is currently ignored for boot args - they will
        always raise ArgumentError if they conflict.
        """
        # TODO: add kwargs to make an option commandline-only or boot-arg-only
        flags = [a for a in args if a.startswith('-')]
        bootargs = [a for a in args if not a.startswith('-')]
        do_bootarg = kwargs.pop("bootarg", True)
        option = super().add_argument(*flags, **kwargs)
        # make a generator that returns only the long opts without the -- prefix
        long_opts = (o[2:] for o in option.option_strings if o.startswith("--"))
        bootargs += (flag for flag in long_opts)
        if do_bootarg:
            for b in bootargs:
                if b in self._boot_arg:
                    raise ArgumentError(
                        "conflicting bootopt string: %s" % b, option)
                else:
                    self._boot_arg[b] = option

        return option

    def _get_bootarg_option(self, arg):
        """
        Find the correct Option for a given bootarg (if one exists)

        :param string arg: boot option

        :returns: argparse option object or None if no suitable option is found
        :rtype argparse option or None
        """
        prefixed_option = False

        if self.bootarg_prefix and arg.startswith(self.bootarg_prefix):
            prefixed_option = True
            arg = arg[len(self.bootarg_prefix):]

        option = self._boot_arg.get(arg)

        # From Fedora 34 this prefix is required. However, leave the code here for some time to
        # tell users that we are ignoring the old variants.
        if self.require_prefix and not prefixed_option:
            return None

        return option

    def parse_boot_cmdline(self, boot_cmdline):
        """
        Parse the boot cmdline and create an appropriate Namespace instance
        according to the option definitions set by add_argument.

        boot_cmdline can be given as a string (to be parsed by KernelArguments), or a
        dict (or any object with .items()) of {bootarg:value} pairs.

        If boot_cmdline is None, the boot_cmdline data will be whatever KernelArguments reads
        by default (/proc/cmdline, /run/initramfs/etc/cmdline, /etc/cmdline).

        If an option requires a value but the boot arg doesn't provide one,
        we'll quietly not set anything in the Namespace. We also skip any boot options
        that were not specified by add_argument as we don't care about them
        (there will usually be quite a lot of them (rd.*, etc.).

        :param boot_cmdline: the Anaconda boot command line arguments
        :type boot_cmdline: string, dict or None

        :returns: an argparse Namespace instance
        :rtype: Namespace
        """
        namespace = Namespace()

        if boot_cmdline is None:
            bootargs = KernelArguments.from_defaults()
        elif isinstance(boot_cmdline, str):
            bootargs = KernelArguments.from_string(boot_cmdline)
        else:
            bootargs = boot_cmdline

        # go over all options corresponding to current boot cmdline
        # and do any modifications necessary
        # NOTE: program cmdline overrides boot cmdline
        for arg, val in bootargs.items_raw():
            option = self._get_bootarg_option(arg)
            if option is None:
                # this boot option is unknown to Anaconda, skip it
                continue
            if option.nargs != 0 and val is None:
                # nargs == 0 -> the option expects one or more arguments but the
                # boot option was not given any, so we skip it
                log.warning("boot option specified without expected number of "
                            "arguments and will be ignored: %s", arg)
                continue
            elif option.nargs == 0 and option.const is not None:
                # nargs == 0 & constr == True -> store_true
                # (we could also check the class, but it begins with an
                # underscore, so it would be ugly)
                # special case: "mpath=0" would otherwise set mpath to True
                if option.const is True and val in ("0", "no", "off"):
                    setattr(namespace, option.dest, False)
                # Set all other set_const cases to the const specified
                else:
                    setattr(namespace, option.dest, option.const)

                # anaconda considers cases such as noselinux=off to be a negative
                # concord, which is to say that selinux will be set to False and
                # we hate you.

                continue
            elif isinstance(val, list):
                for item in val:
                    option(self, namespace, item)
                continue

            option(self, namespace, val)
        return namespace

    # pylint: disable=arguments-renamed
    def parse_args(self, args=None, boot_cmdline=None):
        """
        Like ArgumentParser.parse_args(), but also parses the boot cmdline.
        (see parse_boot_cmdline for details on that process.)
        Program cmdline arguments will override boot cmdline arguments.

        :param args: program command line arguments
        :type args: string or None

        :param boot_cmdline: the Anaconda boot command line arguments
        :type boot_cmdline: string, dict or None

        :returns: an argparse Namespace instance
        :rtype: Namespace
        """
        # parse boot options first
        namespace = self.parse_boot_cmdline(boot_cmdline)
        # parse CLI arguments (if any) and add them to the namespace
        # created from parsing boot options, overriding any options
        # with the same destination already present in the namespace
        # NOTE: this means that CLI options override boot options
        namespace = super().parse_args(args, namespace)
        return namespace


def name_path_pairs(image_specs):
    """Processes and verifies image file specifications. Generates pairs
       of names and paths.

       :param image_specs: a list of image specifications
       :type image_specs: list of str

       Each image spec in image_specs has format <path>[:<name>] where
       <path> is the path to a local file and <name> is an optional
       name used to identify the disk in UI. <name> may not contain colons
       or slashes.

       If no name given in specification, synthesizes name from basename
       of path. Since two distinct paths may have the same basename, handles
       name collisions by synthesizing a different name for the colliding
       name.

       Raises an exception if:
         * A path is empty
         * A path specifies a non-existant file
         * A path specifies a directory
         * Duplicate paths are specified
         * A name contains a "/"
    """
    image_specs = (spec.rsplit(":", 1) for spec in image_specs)
    path_name_pairs = ((image_spec[0], image_spec[1].strip() if len(image_spec) == 2 else None) for image_spec in image_specs)

    paths_seen = []
    names_seen = []
    for (path, name) in path_name_pairs:
        if path == "":
            raise ValueError("empty path specified for image file")
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise ValueError("non-existant path %s specified for image file" % path)
        if os.path.isdir(path):
            raise ValueError("directory path %s specified for image file" % path)
        if path in paths_seen:
            raise ValueError("path %s specified twice for image file" % path)
        paths_seen.append(path)

        if name and "/" in name:
            raise ValueError("improperly formatted image file name %s, includes slashes" % name)

        if not name:
            name = os.path.splitext(os.path.basename(path))[0]

        if name in names_seen:
            for n in itertools.count():
                candidate = "%s_%d" % (name, n)
                if candidate not in names_seen:
                    name = candidate
                    break
        names_seen.append(name)

        yield name, path


class HelpTextParser:
    """Class to parse help text from file and make it available to option
       parser.
    """

    def __init__(self, path):
        """ Initializer
            :param path: The absolute path to the help text file
        """
        self._path = path

        self._help_text = None

    def read(self, lines):
        """Reads option, help text pairs from a text file.

           Each pair is separated from the next by an empty line.
           The option comes first, followed by any number of lines of help text.

           :param lines: a sequence of lines of text
        """
        if not lines:
            return
        expect_option = True
        option = None
        text = []
        for line in (line.strip() for line in lines):
            if line == "":
                expect_option = True
            elif expect_option:
                if option:
                    yield option, " ".join(text)
                option = line
                text = []
                expect_option = False
            else:
                text.append(line)
        yield option, " ".join(text)

    def help_text(self, option):
        """
        Returns the help text corresponding to the given command-line option.
        If no help text is available, returns the empty string.

        :param str option: The name of the option

        :rtype: str
        """
        if self._help_text is None:
            self._help_text = {}
            try:
                with open(self._path) as lines:
                    for parsed_option, parsed_text in self.read(lines):
                        self._help_text[parsed_option] = parsed_text
            except OSError as e:
                log.error("error reading help text file %s: %s", self._path, e)

        return self._help_text.get(option, "")


def getArgumentParser(version_string, boot_cmdline=None):
    """Return the anaconda argument parser.

       :param str version_string: The version string, e.g. 23.19.5.
       :param KernelArguments boot_cmdline: The boot command line options
       :rtype: AnacondaArgumentParser
    """

    datadir = os.environ.get("ANACONDA_DATADIR", "/usr/share/anaconda")

    # NOTE: for each long option (like '--repo'), AnacondaOptionParser
    # checks the boot arguments for bootarg_prefix+option ('inst.repo').
    # If require_prefix is False, it also accepts the option without the
    # bootarg_prefix ('repo').
    # See anaconda_optparse.py and KernelArguments (in flags.py) for details.
    ap = AnacondaArgumentParser(bootarg_prefix="inst.", require_prefix=True)
    help_parser = HelpTextParser(os.path.join(datadir, "anaconda_options.txt"))

    # NOTE: store_false options will *not* get negated when the user does
    # "option=0" on the boot commandline (store_true options do, though).
    # Basically, don't use store_false unless the option starts with "no".

    # YET ANOTHER NOTE: If you change anything here:
    # a) document its usage in docs/boot-options.txt
    # b) be prepared to maintain it for a very long time
    # If this seems like too much trouble, *don't add a new option*!

    # Version
    ap.add_argument('--version', action='version', version="%(prog)s " + version_string)

    class SetCmdlineMode(Action):
        def __call__(self, parser, namespace, values, _option_string=None):
            # We need to save both display mode to TEXT and set noninteractive flag
            setattr(namespace, "display_mode", DisplayModes.TUI)
            setattr(namespace, "noninteractive", True)

    # Interface
    ap.add_argument("-G", "--graphical", dest="display_mode", action="store_const", const=DisplayModes.GUI,
                    default=DisplayModes.GUI, help=help_parser.help_text("graphical"))
    ap.add_argument("-T", "--text", dest="display_mode", action="store_const", const=DisplayModes.TUI,
                    help=help_parser.help_text("text"))
    ap.add_argument("-C", "--cmdline", action=SetCmdlineMode, nargs=0,
                    help=help_parser.help_text("cmdline"))
    ap.add_argument("--noninteractive", dest="noninteractive", action="store_true",
                    help=help_parser.help_text("noninteractive"))

    # Profile
    ap.add_argument("--profile", dest="profile_id", metavar="PROFILE_ID",
                    default="", help=help_parser.help_text("profile"))

    # Network
    ap.add_argument("--proxy", metavar='PROXY_URL', help=help_parser.help_text("proxy"))

    class SetWaitfornet(Action):
        def __call__(self, parser, namespace, values, _option_string=None):
            value = None
            try:
                ivalue = int(values)
            except ValueError:
                pass
            else:
                if ivalue > 0:
                    value = ivalue
            if value is None:
                value = 0
            setattr(namespace, self.dest, value)

    ap.add_argument("--waitfornet", dest="waitfornet", metavar="TIMEOUT_IN_SECONDS",
                    action=SetWaitfornet, help=help_parser.help_text("waitfornet"))

    # Method of operation
    ap.add_argument("-d", "--debug", dest="debug", action="store_true",
                    default=False, help=help_parser.help_text("debug"))
    ap.add_argument("--ks", dest="ksfile", action="store_const",
                    metavar="KICKSTART_URL", const="/run/install/ks.cfg",
                    help=help_parser.help_text("ks"))
    ap.add_argument("--kickstart", dest="ksfile", metavar="KICKSTART_PATH",
                    help=help_parser.help_text("kickstart"))
    ap.add_argument("--ksstrict", dest="ksstrict", action="store_true",
                    default=False, help=help_parser.help_text("ksstrict"))
    ap.add_argument("--rescue", dest="rescue", action="store_true", default=False,
                    help=help_parser.help_text("rescue"))
    ap.add_argument("--armplatform", dest="armPlatform", type=str, metavar="PLATFORM_ID",
                    help="This option is deprecated.")
    ap.add_argument("--multilib", dest="multiLib", action="store_true", default=False,
                    help=help_parser.help_text("multilib"))
    ap.add_argument("--repo", dest="method", default=None, metavar="REPO_URL",
                    help=help_parser.help_text("repo"))
    ap.add_argument("--stage2", dest="stage2", default=None, metavar="STAGE2_URL",
                    help=help_parser.help_text("stage2"))

    class ParseAddRepo(Action):
        def __call__(self, parser, namespace, values, _option_string=None):
            try:
                name, rest = values.split(',', maxsplit=1)
            except ValueError:
                raise ValueError(
                    "The addrepo option has incorrect format ('{}'). "
                    "Use: inst.addrepo=<name>,<url>".format(values)
                ) from None

            items = getattr(namespace, self.dest, self.default)
            items.append((name, rest))
            setattr(namespace, self.dest, items)

    ap.add_argument("--addrepo", dest="addRepo", default=[], metavar="NAME,ADDITIONAL_REPO_URL",
                    action=ParseAddRepo, help=help_parser.help_text("addrepo"))
    ap.add_argument("--noverifyssl", action="store_true", default=False,
                    help=help_parser.help_text("noverifyssl"))
    ap.add_argument("--liveinst", action="store_true", default=False,
                    help=help_parser.help_text("liveinst"))

    # Display
    ap.add_argument("--resolution", dest="runres", default=None, metavar="WIDTHxHEIGHT",
                    help=help_parser.help_text("resolution"))
    ap.add_argument("--xtimeout", dest="xtimeout", action="store", type=int, default=X_TIMEOUT,
                    metavar="TIMEOUT_IN_SECONDS", help=help_parser.help_text("xtimeout"))
    ap.add_argument("--rdp", action="store_true", default=False, dest="rdp_enabled",
                    help=help_parser.help_text("rdp"))
    ap.add_argument("--rdp.username", default="", metavar="USERNAME", dest="rdp_username",
                    help=help_parser.help_text("rdp.username"))
    ap.add_argument("--rdp.password", default="", metavar="PASSWORD", dest="rdp_password",
                    help=help_parser.help_text("rdp.password"))

    # Language
    ap.add_argument("--keymap", metavar="KEYMAP", help=help_parser.help_text("keymap"))
    ap.add_argument("--lang", metavar="LANG", help=help_parser.help_text("lang"))

    # Obvious
    ap.add_argument("--syslog", metavar="HOST[:PORT]", help=help_parser.help_text("syslog"))
    ap.add_argument("--remotelog", metavar="HOST:PORT", help=help_parser.help_text("remotelog"))
    ap.add_argument("--virtiolog", metavar="/dev/virtio-ports/NAME", default=VIRTIO_PORT,
                    help=help_parser.help_text("virtiolog"))

    from pykickstart.constants import SELINUX_DISABLED, SELINUX_ENFORCING

    from pyanaconda.core.constants import SELINUX_DEFAULT
    ap.add_argument("--noselinux", dest="selinux", action="store_const",
                    const=SELINUX_DISABLED, default=SELINUX_DEFAULT,
                    help=help_parser.help_text("noselinux"))

    # Use a custom action to convert --selinux=0 and --selinux=1 into the
    # appropriate constants
    class ParseSelinux(Action):
        def __call__(self, parser, namespace, values, _option_string=None):
            if values == "0":
                setattr(namespace, self.dest, SELINUX_DISABLED)
            else:
                setattr(namespace, self.dest, SELINUX_ENFORCING)

    ap.add_argument("--selinux", action=ParseSelinux, nargs="?", help=help_parser.help_text("selinux"))

    ap.add_argument("--mpath", action="store_true", help=help_parser.help_text("mpath"))

    ap.add_argument("--disklabel", default=SUPPRESS, help=help_parser.help_text("disklabel"))
    ap.add_argument("--gpt", dest="disklabel", action="store_const", const="gpt",
                    default=SUPPRESS, help=help_parser.help_text("gpt"))

    ap.add_argument("--noibft", dest="ibft", action="store_false", default=True,
                    help=help_parser.help_text("noibft"))
    ap.add_argument("--ibft", action="store_true", help=help_parser.help_text("ibft"))
    ap.add_argument("--nonibftiscsiboot", action="store_true", default=False,
                    help=help_parser.help_text("nonibftiscsiboot"))

    # Geolocation
    ap.add_argument("--geoloc", metavar="PROVIDER_ID", help=help_parser.help_text("geoloc"))
    ap.add_argument("--geoloc-use-with-ks", action="store_true", default=False,
                    help=help_parser.help_text("geoloc-use-with-ks"))

    # Kickstart and log saving
    # - use a custom action to convert the values of the nosave option into appropriate flags
    class ParseNosave(Action):
        def __call__(self, parser, namespace, values, _option_string=None):
            options = []
            if values:
                options = values.split(",")
            if "all" in options:
                namespace.can_copy_input_kickstart = False
                namespace.can_save_output_kickstart = False
                namespace.can_save_installation_logs = False
            else:
                if "all_ks" in options:
                    namespace.can_copy_input_kickstart = False
                    namespace.can_save_output_kickstart = False
                else:
                    if "input_ks" in options:
                        namespace.can_copy_input_kickstart = False
                    if "output_ks" in options:
                        namespace.can_save_output_kickstart = False
                if "logs" in options:
                    namespace.can_save_installation_logs = False

    ap.add_argument("--nosave", action=ParseNosave, nargs="?", help=help_parser.help_text("nosave"))

    # Miscellaneous
    ap.add_argument("--nomount", dest="rescue_nomount", action="store_true", default=False,
                    help=help_parser.help_text("nomount"))
    ap.add_argument("--updates", dest="updates_url", action="store", type=str,
                    metavar="UPDATES_URL", help=help_parser.help_text("updates"))
    ap.add_argument("--image", action="append", dest="images", default=[],
                    metavar="IMAGE_SPEC", help=help_parser.help_text("image"))
    ap.add_argument("--dirinstall", nargs="?",
                    const=os.environ.get("ANACONDA_ROOT_PATH", "/mnt/sysimage"),
                    help=help_parser.help_text("dirinstall"))
    ap.add_argument("--memcheck", action="store_true", default=True,
                    help=help_parser.help_text("memcheck"))
    ap.add_argument("--nomemcheck", action="store_false", dest="memcheck",
                    help=help_parser.help_text("nomemcheck"))
    ap.add_argument("--leavebootorder", action="store_true", default=False,
                    help=help_parser.help_text("leavebootorder"))
    ap.add_argument("--noeject", action="store_false", dest="eject", default=True,
                    help=help_parser.help_text("noeject"))
    ap.add_argument("--extlinux", action="store_true", default=False,
                    help=help_parser.help_text("extlinux"))
    ap.add_argument("--sdboot", action="store_true", default=False,
                    help=help_parser.help_text("sdboot"))
    ap.add_argument("--nombr", action="store_true", default=False,
                    help=help_parser.help_text("nombr"))
    ap.add_argument("--mpathfriendlynames", dest="multipath_friendly_names", action="store_true",
                    default=True, help=help_parser.help_text("mpathfriendlynames"))
    ap.add_argument("--kexec", action="store_true", default=False,
                    help=help_parser.help_text("kexec"))

    # some defaults change based on cmdline flags
    if boot_cmdline is not None:
        if "console" in boot_cmdline:
            ap.set_defaults(display_mode=DisplayModes.TUI)

    return ap

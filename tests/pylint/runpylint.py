#!/usr/bin/python3

import atexit
import os
import shutil
import sys
import tempfile
import time
from os import path

from censorship import CensorshipConfig, CensorshipLinter, FalsePositive

TIME_LOG = "pylint-time.log"


class AnacondaLintConfig(CensorshipConfig):
    def __init__(self):
        super().__init__()

        current_dir = os.path.dirname(os.path.realpath(__file__))

        self.pylintrc_path = os.path.join(current_dir, "pylintrc")

        gtk_instance_classes = [
            "Accordion",
            "Box",
            "Builder",
            "ComboBox",
            "Cursor",
            "CustomListBoxRow",
            "EnvironmentListBoxRow",
            "GraphicalUserInterface",
            "IconSize",
            "IconTheme",
            "MainWindow",
            "MessageDialog",
            "Page",
            "SeparatorRow",
            "StyleContext",
            "UnknownPage",
        ]
        gi_repository_instance_classes = [
            "TransactionOperationType",
            "LogLevelFlags",
        ]

        self.false_positives = [
            FalsePositive(r"^E1101.*: Instance of 'KickstartSpecificationHandler' has no '.*' member$"),

            # TODO: BlockDev introspection needs to be added to pylint to handle these
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_is_fba' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_needs_format' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_format' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'sanitize_dev_input' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'zfcp_sanitize_wwpn_input' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'zfcp_sanitize_lun_input' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'name_from_node' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'generate_backup_passphrase' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_is_ldl' member"),
            FalsePositive(r"I1101.*: Module 'gi.repository.BlockDev' has no 'loop_get_backing_file' member"),
            FalsePositive(r"E1120.*: _load_plugin_s390: No value for argument 'self' in function call"),

            # TODO: NM introspection needs to be added to pylint to handle these
            # https://github.com/pylint-dev/pylint/issues/10433
            FalsePositive(r"E1120.*(?:network\.py|nm_client\.py|test_module_network_nm_client\.py|glib\.py|device_configuration\.py):.* No value for argument 'self' in .* call"),
            FalsePositive(r"E1101.*(?:network\.py|nm_client\.py):.* Class .* has no .* member"),

            # TODO: OStree introspection needs to be added to pylint to handle these
            FalsePositive(r"E1120.*: PullRemoteAndDeleteTask.run: No value for argument 'self' in unbound method call"),

            # TODO: GTK introspection needs to be added to pylint to handle these
            FalsePositive(r"E1120.*(?:MainWindow|GraphicalUserInterface|busyCursor|unbusyCursor|setup_gtk_direction|CreateNewPage|LangLocaleHandler).* No value for argument 'self' in .* call"),
            FalsePositive(fr"E1101.*(?:{'|'.join(gtk_instance_classes)}).* has no .* member.*"),

            # TODO: GI Repository introspection needs to be added to pylint to handle these
            FalsePositive(fr"E1101.*(?:{'|'.join(gi_repository_instance_classes)}).* has no .* member.*"),
            FalsePositive(r"I1101.* Module 'gi.repository.Gtk'.* has no .* member.*"),
            FalsePositive(r"I1101.* Module 'gi.repository.Gdk'.* has no .* member.*"),
        ]

    def _files(self):
        srcdir = os.environ.get("top_srcdir", os.getcwd())

        retval = self._get_py_paths(srcdir)

        return retval

    def _get_py_paths(self, directory):
        retval = []

        for (root, dirnames, files) in os.walk(directory):

            # skip scanning of already added python modules
            if any(root.startswith(i) for i in retval):
                continue

            if "__init__.py" in files:
                retval.append(root)
                continue

            for f in files:
                try:
                    with open(root + "/" + f) as fo:
                        line = fo.readline(1024)
                except (UnicodeDecodeError, FileNotFoundError):
                    # If we couldn't open this file, just skip it.  It wasn't
                    # going to be valid python anyway.
                    continue

                # Test only files which meets these conditions:
                # Ignore j2 files which are input for template rendering
                if not f.endswith(".j2"):
                    # Either ends in .py or contains #!/usr/bin/python in the first line.
                    if f.endswith(".py") or \
                       (line and str(line).startswith("#!/usr/bin/python")):
                        retval.append(root + "/" + f)

        return retval

    @property
    def check_paths(self):
        return self._files()


def setup_environment():
    # We need top_builddir to be set so we know where to put the pylint analysis
    # stuff.  Usually this will be set up if we are run via "make test" but if
    # not, hope that we are at least being run out of the right directory.
    builddir = os.environ.get("top_builddir", os.getcwd())

    # XDG_RUNTIME_DIR is "required" to be set, so make one up in case something
    # actually tries to do something with it.
    if "XDG_RUNTIME_DIR" not in os.environ:
        d = tempfile.mkdtemp()
        os.environ["XDG_RUNTIME_DIR"] = d
        atexit.register(_del_xdg_runtime_dir)

    # Unset TERM so that things that use readline don't output terminal garbage.
    if "TERM" in os.environ:
        os.environ.pop("TERM")

    # Don't try to connect to the accessibility socket.
    os.environ["NO_AT_BRIDGE"] = "1"

    # Force the GDK backend to Wayland.  Otherwise if no display can be found, Gdk
    # tries every backend type, which includes "broadway", which prints an error
    # and keeps changing the content of said error.
    os.environ["GDK_BACKEND"] = "wayland"

    # Save analysis data in the pylint directory.
    os.environ["PYLINTHOME"] = builddir + "/tests/pylint/.pylint.d"
    if not os.path.exists(os.environ["PYLINTHOME"]):
        os.mkdir(os.environ["PYLINTHOME"])


def _del_xdg_runtime_dir():
    shutil.rmtree(os.environ["XDG_RUNTIME_DIR"])


def _get_timelog_path():
    log_dir = path.dirname(path.realpath(__file__))
    return "{}/{}".format(log_dir, TIME_LOG)


def save_start_time():
    lt = time.localtime()
    with open(_get_timelog_path(), 'at') as f:
        f.write("Start - {}:{}:{}\n".format(lt.tm_hour, lt.tm_min, lt.tm_sec))


def save_end_time():
    lt = time.localtime()
    with open(_get_timelog_path(), 'at') as f:
        f.write("End - {}:{}:{}\n".format(lt.tm_hour, lt.tm_min, lt.tm_sec))


if __name__ == "__main__":
    setup_environment()
    conf = AnacondaLintConfig()
    linter = CensorshipLinter(conf)
    save_start_time()
    rc = linter.run()
    save_end_time()
    sys.exit(rc)

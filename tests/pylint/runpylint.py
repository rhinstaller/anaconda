#!/usr/bin/python3

import atexit
import shutil
import sys
import tempfile
import time
import os

from os import path

from censorship import CensorshipConfig, CensorshipLinter, FalsePositive

TIME_LOG = "pylint-time.log"


class AnacondaLintConfig(CensorshipConfig):
    def __init__(self):
        super().__init__()

        current_dir = os.path.dirname(os.path.realpath(__file__))

        self.pylintrc_path = os.path.join(current_dir, "pylintrc")

        self.false_positives = [
            FalsePositive(r"^E1101.*: Instance of 'KickstartSpecificationHandler' has no '.*' member$"),
            FalsePositive(r"^E1101.*: FedoraGeoIPProvider._refresh: Instance of 'LookupDict' has no 'ok' member"),
            FalsePositive(r"^E1101.*: HostipGeoIPProvider._refresh: Instance of 'LookupDict' has no 'ok' member"),
            FalsePositive(r"^E1101.*: Geocoder._reverse_geocode_nominatim: Instance of 'LookupDict' has no 'ok' member"),

            # TODO: BlockDev introspection needs to be added to pylint to handle these
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_is_fba' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_needs_format' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_format' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'sanitize_dev_input' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_online' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'zfcp_sanitize_wwpn_input' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'zfcp_sanitize_lun_input' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'name_from_node' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'generate_backup_passphrase' member"),
            FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_is_ldl' member"),
        ]

    def _files(self):
        srcdir = os.environ.get("top_srcdir", os.getcwd())

        retval = self._get_py_paths(srcdir)

        return retval

    def _get_py_paths(self, directory):
        retval = []

        for (root, dirnames, files) in os.walk(directory):

            # skip scanning of already added python modules
            skip = False
            for i in retval:
                if root.startswith(i):
                    skip = True
                    break

            if skip:
                continue

            if "__init__.py" in files:
                retval.append(root)
                continue

            for f in files:
                try:
                    with open(root + "/" + f) as fo:
                        lines = fo.readlines()
                except UnicodeDecodeError:
                    # If we couldn't open this file, just skip it.  It wasn't
                    # going to be valid python anyway.
                    continue

                # Test only files which meets these conditions:
                # Ignore j2 files which are input for template rendering
                if not f.endswith(".j2"):
                    # Either ends in .py or contains #!/usr/bin/python in the first line.
                    if f.endswith(".py") or \
                       (lines and str(lines[0]).startswith("#!/usr/bin/python")):
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

    # Force the GDK backend to X11.  Otherwise if no display can be found, Gdk
    # tries every backend type, which includes "broadway", which prints an error
    # and keeps changing the content of said error.
    os.environ["GDK_BACKEND"] = "x11"

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

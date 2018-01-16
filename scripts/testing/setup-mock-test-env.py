#!/bin/python3
#
# Setup mock testing environment for Anaconda.
#

import os
import sys
import subprocess

from argparse import ArgumentParser


DEPENDENCY_SOLVER = "dependency_solver.py"

ANACONDA_MOCK_PATH = "/anaconda"


class MockException(Exception):

    def __init__(self, message, cmd):
        msg = """When running command '{}' exception raised.
        {}
        """.format(cmd, message)
        super().__init__(msg)


def _prepare_command(mock_command):
    cmd = []
    cmd.extend(mock_command)

    return cmd


def _run_cmd_in_chroot(mock_command):
    mock_command.append('--chroot')
    mock_command.append('--')

    return mock_command


def _get_script_dir():
    return os.path.dirname(os.path.realpath(__file__))


def _resolve_top_dir():
    script_dir = _get_script_dir()
    # go up two dirs to get top path
    top_dir = os.path.split(script_dir)[0]
    return os.path.split(top_dir)[0]


def _check_dir_exists(path):
    if os.path.exists(path):
        print("The result dir {} must not exists!".format(path), file=sys.stderr)
        exit(1)


def _check_subprocess(cmd, error_msg, stdout_pipe=False):
    """Call external command and verify return result."""
    process_result = _call_subprocess(cmd, stdout_pipe)

    if process_result.returncode != 0:
        raise MockException(error_msg, cmd)

    return process_result


def _call_subprocess(cmd, stdout_pipe=False):
    """Call external command and return result."""
    print("Running command {}".format(cmd))

    if stdout_pipe:
        return subprocess.run(cmd, stdout=subprocess.PIPE)
    else:
        return subprocess.run(cmd)


def parse_args():
    parser = ArgumentParser(description="""Setup Anaconda test environment in mock.""")
    parser.add_argument('mock_config', action='store', type=str, metavar='mock-config',
                        help="""
                        mock configuration file; could be specified as file path or 
                        name of the file in /etc/mock without .cfg suffix
                        """)
    parser.add_argument('--init', action='store_true', dest='init',
                        help="""initialize environment with the required packages""")
    parser.add_argument('--install', '-i', action='store', type=str, dest='install',
                        help="""install additional packages to the mock""")
    parser.add_argument('--uniqueext', action='store', type=str, dest='uniqueext',
                        help="""
                        set suffix to mock chroot dir; this must be used to 
                        run parallel tasks.
                        """)
    parser.add_argument('--run-tests', '-t', action='store_true', dest='run_tests',
                        help="""
                        run anaconda tests in a mock
                        """)
    parser.add_argument('--copy', '-c', action='store_true', dest='copy',
                        help="""
                        keep existing mock and only replace Anaconda folder in it;
                        this will not re-init mock chroot
                        """)
    parser.add_argument('--result', action='store', type=str, metavar='folder',
                        dest='result_folder', default=None,
                        help="""
                        save test result folder from anaconda to destination folder
                        """)

    return parser.parse_args()


def get_required_packages():
    """Get required packages for running Anaconda tests."""
    script = _get_script_dir() + os.path.sep + DEPENDENCY_SOLVER
    cmd = [script]

    proc_res = _check_subprocess(cmd, "Can't call dependency_solver script.", stdout_pipe=True)

    return proc_res.stdout.decode('utf-8').strip()


def install_required_packages(mock_command):
    packages = get_required_packages()
    install_packages_to_mock(mock_command, packages)


def remove_anaconda_in_mock(mock_command):
    cmd = _prepare_command(mock_command)

    cmd = _run_cmd_in_chroot(cmd)
    cmd.append('rm -rf ' + ANACONDA_MOCK_PATH)

    _check_subprocess(cmd, "Can't remove existing anaconda.")


def copy_anaconda_to_mock(mock_command):
    remove_anaconda_in_mock(mock_command)

    anaconda_dir = _resolve_top_dir()
    cmd = _prepare_command(mock_command)

    cmd.append('--copyin')
    cmd.append('{}'.format(anaconda_dir))
    cmd.append(ANACONDA_MOCK_PATH)

    _check_subprocess(cmd, "Can't copy Anaconda to mock.")


def copy_result(mock_command, out_dir):
    cmd = _prepare_command(mock_command)

    cmd.append('--copyout')
    cmd.append('{}/result'.format(ANACONDA_MOCK_PATH))
    cmd.append(out_dir)

    _check_subprocess(cmd, "Con't copy Anaconda tests results out of mock. "
                           "Destination folder must not exists!")


def create_mock_command(mock_conf, uniqueext):
    cmd = ['mock', '-r', mock_conf, ]

    if uniqueext:
        cmd.append('--uniqueext')
        cmd.append(uniqueext)

    return cmd


def install_packages_to_mock(mock_command, packages):
    cmd = _prepare_command(mock_command)

    cmd.append('--install')
    cmd.extend(packages.split(" "))

    _check_subprocess(cmd, "Can't install packages to mock.")


def run_tests(mock_command):
    cmd = _prepare_command(mock_command)

    cmd = _run_cmd_in_chroot(cmd)
    cmd.append('cd {} && ./autogen.sh && ./configure'.format(ANACONDA_MOCK_PATH))

    _check_subprocess(cmd, "Can't run tests in a mock.")

    cmd = _prepare_command(mock_command)

    cmd = _run_cmd_in_chroot(cmd)
    cmd.append('cd {} && make ci'.format(ANACONDA_MOCK_PATH))

    _call_subprocess(cmd)


def init_mock(mock_command):
    cmd = _prepare_command(mock_command)

    cmd.append('--init')

    _check_subprocess(cmd, "Can't initialize mock.")


def setup_mock(mock_command):
    init_mock(mock_command)
    install_required_packages(mock_command)


if __name__ == "__main__":
    ns = parse_args()

    mock_cmd = create_mock_command(ns.mock_config, ns.uniqueext)
    mock_init_run = False

    if not any([ns.init, ns.copy, ns.run_tests, ns.install]):
        print("You need to specify one of the main commands!", file=sys.stderr)
        print("Run './setup-mock-test-env.py --help' for more info.", file=sys.stderr)
        exit(1)

    # quit immediately if the result dir exists
    if ns.result_folder:
        _check_dir_exists(ns.result_folder)

    if ns.init:
        setup_mock(mock_cmd)
        mock_init_run = True
        if ns.install:
            install_packages_to_mock(mock_cmd, ns.install)

        cmd_msg = " ".join(mock_cmd)
        print()
        print("mock environment setup successful")
        print("connect to mock by calling:")
        print("{} --shell".format(cmd_msg))
        print("")
        print("start ci by calling:")
        print("setup-mock-test-env.py --copy --run-tests --result /tmp/result {}".format(ns.mock_config))
        print("or manually:")
        print("{} --chroot -- \"cd {} && ./autogen.sh && ./configure && make ci\"".
              format(cmd_msg, ANACONDA_MOCK_PATH))

    if ns.install and not mock_init_run:
        install_packages_to_mock(mock_cmd, ns.install)

    if ns.copy:
        copy_anaconda_to_mock(mock_cmd)

    if ns.run_tests:
        run_tests(mock_cmd)

    if ns.result_folder:
        copy_result(mock_cmd, ns.result_folder)

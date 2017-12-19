#!/bin/python3
#
# Setup mock testing environment for Anaconda.
#

import os
import subprocess

from argparse import ArgumentParser


DEPENDENCY_SOLVER = "dependency_solver.py"


class MockException(Exception):

    def __init__(self, message, cmd):
        msg = """When running command '{}' exception raised.
        {}
        """.format(cmd, message)
        super().__init__(msg)


def _get_script_dir():
    return os.path.dirname(os.path.realpath(__file__))


def _resolve_top_dir():
    script_dir = _get_script_dir()
    # go up two dirs to get top path
    top_dir = os.path.split(script_dir)[0]
    return os.path.split(top_dir)[0]


def _call_subprocess(cmd, error_msg, stdout_pipe=False):
    """Call external command and verify return code."""
    print("Running command {}".format(cmd))

    if stdout_pipe:
        process_result = subprocess.run(cmd, stdout=subprocess.PIPE)
    else:
        process_result = subprocess.run(cmd)

    if process_result.returncode != 0:
        raise MockException(error_msg, cmd)

    return process_result


def parse_args():
    parser = ArgumentParser(description="""Setup Anaconda test environment in mock.""")
    parser.add_argument('mock_config', action='store', type=str, metavar='mock-config',
                        help="""
                        mock configuration file; could be specified as file path or 
                        name of the file in /etc/mock without .cfg suffix
                        """)
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

    return parser.parse_args()


def get_required_packages():
    """Get required packages for running Anaconda tests."""
    script = _get_script_dir() + os.path.sep + DEPENDENCY_SOLVER
    cmd = [script]

    proc_res = _call_subprocess(cmd, "Can't call dependency_solver script.", stdout_pipe=True)

    return proc_res.stdout.decode('utf-8').strip()


def install_required_packages(mock_command):
    packages = get_required_packages()
    install_packages_to_mock(mock_command, packages)


def remove_anaconda_in_mock(mock_command):
    cmd = []

    cmd.extend(mock_command)
    cmd.append('--chroot')
    cmd.append('--')
    cmd.append('rm -rf /anaconda')

    _call_subprocess(cmd, "Can't remove existing anaconda.")


def copy_anaconda_to_mock(mock_command):
    remove_anaconda_in_mock(mock_command)

    anaconda_dir = _resolve_top_dir()
    cmd = []

    cmd.extend(mock_command)
    cmd.append('--copyin')
    cmd.append('{}'.format(anaconda_dir))
    cmd.append('/anaconda')

    _call_subprocess(cmd, "Can't copy Anaconda to mock.")


def create_mock_command(mock_conf, uniqueext):
    cmd = ['mock', '-r', mock_conf, ]

    if uniqueext:
        cmd.append('--uniqueext')
        cmd.append(uniqueext)

    return cmd


def install_packages_to_mock(mock_command, packages):
    cmd = []
    cmd.extend(mock_command)

    cmd.append('--install')
    cmd.extend(packages.split(" "))

    _call_subprocess(cmd, "Can't install packages to mock.")


def run_tests(mock_command):
    cmd = []
    cmd.extend(mock_command)

    cmd.append('--chroot')
    cmd.append('--')
    cmd.append('cd /anaconda && ./autogen.sh && ./configure && make ci')

    _call_subprocess(cmd, "Can't run tests in a mock.")


def init_mock(mock_command):
    cmd = []
    cmd.extend(mock_command)
    cmd.append('--init')

    _call_subprocess(cmd, "Can't initialize mock.")


def setup_mock(mock_command):
    init_mock(mock_command)
    install_required_packages(mock_command)
    copy_anaconda_to_mock(mock_command)


if __name__ == "__main__":
    ns = parse_args()

    mock_cmd = create_mock_command(ns.mock_config, ns.uniqueext)

    if ns.copy:
        copy_anaconda_to_mock(mock_cmd)
    elif ns.run_tests:
        run_tests(mock_cmd)
    else:
        setup_mock(mock_cmd)
        if ns.install:
            install_packages_to_mock(mock_cmd, ns.install)

    cmd_msg = " ".join(mock_cmd)
    print()
    print("mock environment setup successful")
    print("connect to mock by calling:")
    print("{} --shell".format(cmd_msg))
    print("")
    print("start ci by calling:")
    print("setup-mock-test-env.py --run-tests {}".format(ns.mock_config))
    print("or manually:")
    print("{} --chroot -- \"cd /anaconda && ./autogen.sh && ./configure && make ci\"".
          format(cmd_msg))

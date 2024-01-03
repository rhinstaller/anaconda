#!/usr/bin/python3
import argparse
import fcntl
import pam
import pwd
import os
import stat
import struct
import subprocess
import sys

VT_GETSTATE = 0x5603
VT_ACTIVATE = 0x5606
VT_OPENQRY = 0x5600
VT_WAITACTIVE = 0x5607
TIOCSCTTY = 0x540E

def is_running_in_logind_session():
    try:
        with open('/proc/self/loginuid', 'r') as f:
            loginuid = int(f.read().strip())
            return loginuid != 0xFFFFFFFF
    except Exception as e:
        raise Exception(f"Error reading /proc/self/loginuid: {e}")

def find_free_vt():
    with open('/dev/tty0', 'w') as console:
        result = fcntl.ioctl(console, VT_OPENQRY, struct.pack('i', 0))
        vt = struct.unpack('i', result)[0]
        return vt

def run_program_in_new_session(arguments, pam_environment, user, service, tty_input, tty_output, vt):
    pam_handle = pam.pam()

    for key, value in pam_environment.items():
        pam_handle.putenv(f'{key}={value}')

    old_tty_input = os.fdopen(os.dup(0), 'r')
    os.dup2(os.dup(tty_input.fileno()), 0)

    if not pam_handle.authenticate(user, '', service=service, call_end=False):
        raise Exception("Authentication failed")

    for key, value in pam_environment.items():
        pam_handle.putenv(f'{key}={value}')

    if pam_handle.open_session() != pam.PAM_SUCCESS:
        raise Exception("Failed to open PAM session")

    session_environment = os.environ.copy()
    session_environment.update(pam_handle.getenvlist())

    os.dup2(old_tty_input.fileno(), 0)

    user_info = pwd.getpwnam(user)
    uid = user_info.pw_uid
    gid = user_info.pw_gid

    old_tty_output = os.fdopen(os.dup(2), 'w')

    console = open("/dev/tty0", 'w')

    try:
        old_vt = 0
        if vt:
            vt_state = fcntl.ioctl(console, VT_GETSTATE, struct.pack('HHH', 0, 0, 0))
            old_vt, _, _ = struct.unpack('HHH', vt_state)
    except OSError as e:
        print(f"Could not read current VT: {e}", file=old_tty_output)

    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
        except OSError as e:
            print(f"Could not create new pid session: {e}", file=old_tty_output)

        try:
            fcntl.ioctl(tty_output, TIOCSCTTY, 1)
        except OSError as e:
            print(f"Could not take control of tty: {e}", file=old_tty_output)

        try:
            fcntl.ioctl(console, VT_ACTIVATE, vt)
        except OSError as e:
            print(f"Could not change to VT {vt}: {e}", file=old_tty_output)

        try:
            fcntl.ioctl(console, VT_WAITACTIVE, vt)
        except OSError as e:
            print(f"Could not wait for VT {vt} to change: {e}", file=old_tty_output)

        try:
            os.dup2(tty_input.fileno(), 0)
            os.dup2(tty_output.fileno(), 1)
            os.dup2(tty_output.fileno(), 2)
        except OSError as e:
            print(f"Could not set up standard i/o: {e}", file=old_tty_output)

        try:
            os.initgroups(user, gid)
            os.setgid(gid)
            os.setuid(uid);
        except OSError as e:
            print(f"Could not become user {user} (uid={uid}): {e}", file=old_tty_output)

        try:
            os.execvpe(arguments[0], arguments, session_environment)
        except OSError as e:
            print(f"Could not run program \"{' '.join(arguments)}\": {e}", file=old_tty_output)
        os._exit(1)

    try:
        (_, exit_code) = os.waitpid(pid, 0);
    except KeyboardInterrupt:
        os.kill(pid, os.SIGINT)
    except OSError as e:
        print(f"Could not wait for program to finish: {e}", file=old_tty_output)

    try:
        if old_vt:
            fcntl.ioctl(console, VT_ACTIVATE, old_vt)
            fcntl.ioctl(console, VT_WAITACTIVE, old_vt)
    except OSError as e:
        print(f"Could not change VTs back: {e}", file=old_tty_output)

    if os.WIFEXITED(exit_code):
        exit_code = os.WEXITSTATUS(exit_code)
    else:
        os.kill(os.getpid(), os.WTERMSIG(exit_code))
    old_tty_output.close()
    console.close()

    if pam_handle.close_session() != pam.PAM_SUCCESS:
        raise Exception("Failed to close PAM session")

    pam_handle.end()

    return exit_code

def main():
    parser = argparse.ArgumentParser(description='Run a program in a PAM session with specific environment variables as a specified user.')
    parser.add_argument('--user', default='root', help='Username for which to run the program')
    parser.add_argument('--service', default='su-l', help='PAM service to use')
    parser.add_argument('--session-type', default='x11', help='e.g., x11, wayland, or tty')
    parser.add_argument('--session-class', default='user', help='e.g., greeter or user')
    parser.add_argument('--session-desktop', help='desktop file id associated with session, e.g. gnome, gnome-classic, gnome-wayland')
    parser.add_argument('--vt', help='VT to run on')

    args, remaining_args = parser.parse_known_args()

    if not remaining_args:
        remaining_args = [ "bash", "-l" ]

    if not args.vt:
        vt = find_free_vt()
        print(f'Using VT {vt}')
    else:
        vt = int(args.vt)

    if is_running_in_logind_session():
        program = ['systemd-run',
                   f'--unit=run-in-new-session-{os.getpid()}.service',
                   '--pipe',
                   '--wait',
                   '-d']

        program += [sys.executable]
        program += sys.argv
        subprocess.run(program)
        return

    try:
        tty_path = f'/dev/tty{vt}'
        tty_input = open(tty_path, 'r')
        tty_output = open(tty_path, 'w')

        pam_environment = {}
        pam_environment['XDG_SEAT'] = "seat0"
        pam_environment['XDG_SESSION_TYPE'] = args.session_type
        pam_environment['XDG_SESSION_CLASS'] = args.session_class
        pam_environment['XDG_SESSION_DESKTOP'] = args.session_desktop
        pam_environment['XDG_VTNR'] = vt

        try:
            result = run_program_in_new_session(remaining_args, pam_environment, args.user, args.service, tty_input, tty_output, vt)
        except OSError as e:
            raise Exception(f"Error running program \"{' '.join(remaining_args)}\": {e}")
        tty_input.close()
        tty_output.close()
        sys.exit(result)
    except OSError as e:
        raise Exception(f"Error opening tty associated with VT {vt}: {e}")

if __name__ == '__main__':
    main()


/*
 * isys.c
 *
 * Copyright (C) 2007, 2008, 2009  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "config.h"
#include <Python.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <execinfo.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <syslog.h>

static PyObject * doSignalHandlers(PyObject *s, PyObject *args);
static PyObject * doSetSystemTime(PyObject *s, PyObject *args);

static PyMethodDef isysModuleMethods[] = {
    { "installSyncSignalHandlers", doSignalHandlers, METH_NOARGS, "Install synchronous signal handlers"},
    { "set_system_time", doSetSystemTime, METH_VARARGS, "set system time"},
    { NULL, NULL, 0, NULL }
};

static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "isys",
        "The Anaconda isys module",
        -1,
        isysModuleMethods,
};

PyMODINIT_FUNC
// cppcheck-suppress unusedFunction
PyInit__isys(void) {
    return PyModule_Create(&moduledef);
}

static void sync_signal_handler(int signum) {
    void *array[20];
    size_t size;

    sigset_t sigset;

    pid_t child_pid;
    char *pid_str;
    int pid_size;
    int exit_status;

    /* Doing stuff in signal handlers is tricky. The program has been
     * interupted, probably in the middle of something going wrong with
     * memory access, so we're in a weird state to begin with, and errors
     * that happen during the signal handler can cause some gnarly things
     * to happen.
     *
     * POSIX defines a set of functions (listed in man 7 signal) that are
     * safe to call from within a signal handler, and glibc adds a few more.
     * Do the safe things first, then reset the signal handler so that further
     * receipts of the signal (probably SIGSEGV) will just crash the program
     * instead of getting stuck in a loop, and then enter the danger zone.
     */

    /* First say that something went wrong. That's easy! (but we can't use printf or strlen) */
    const char err_prefix[] = "Anaconda received signal ";
    char sigstr[2];
    write(STDOUT_FILENO, err_prefix, sizeof(err_prefix) - 1);

    /* Convert signum to ascii without using anything that allocates memory */
    /* Assume the signal is <= 99 */
    sigstr[0] = (signum / 10 % 10) + '0';
    sigstr[1] = (signum % 10) + '0';
    write(STDOUT_FILENO, sigstr, sizeof(sigstr));
    write(STDOUT_FILENO, "!.\n", 3);

    /* And that's about all the safe things we can do. Time to reset the handler,
     * unblock the signal and go wild */
    signal(signum, SIG_DFL);
    sigemptyset(&sigset);
    sigaddset(&sigset, signum);
    pthread_sigmask(SIG_UNBLOCK, &sigset, NULL);

    /* Print the backtrace */
    /* backtrace_symbols_fd is signal-safe, but backtrace is not. */
    size = backtrace (array, 20);
    backtrace_symbols_fd(array, size, STDOUT_FILENO);

    /* Log the crash. Hopefully this is happening after logging has started
     * and livemedia-creator will get the message. */
    openlog("anaconda", 0, LOG_USER);
    syslog(LOG_CRIT, "Anaconda crashed on signal %d", signum);
    closelog();


    /* Try call gcore on ourself to write out a core file */
    pid_size = snprintf(NULL, 0, "%d", getpid());
    if (pid_size <= 0) {
        perror("Unable to current PID");
        exit(1);
    }
    pid_size++;
    pid_str = malloc(pid_size);
    snprintf(pid_str, pid_size, "%d", getpid());

    child_pid = fork();
    if (0 == child_pid) {
        /* Disable stderr to suppress all the garbage about debuginfo packages */
        int fd;
        fd = open("/dev/null", O_WRONLY);
        if (fd < 0) {
            perror("Unable to open /dev/null");
            exit(1);
        }
        dup2(fd, STDERR_FILENO);

        execlp("gcore", "gcore", "-o", "/tmp/anaconda.core", pid_str, NULL);
        perror("Unable to exec gcore");
        exit(1);
    }
    else if (child_pid < 0) {
        perror("Unable to fork");
        exit(1);
    }

    if (waitpid(child_pid, &exit_status, 0) < 0) {
        perror("Error waiting on gcore");
        exit(1);
    }

    if (!WIFEXITED(exit_status) || WEXITSTATUS(exit_status) != 0) {
        printf("gcore exited with status %d\n", exit_status);
        exit(1);
    }

    exit(1);
}

static PyObject * doSignalHandlers(PyObject *s, PyObject *args) {
    /* Install a signal handler for all synchronous signals */
    struct sigaction sa;

    memset(&sa, 0, sizeof(struct sigaction));
    sa.sa_handler = sync_signal_handler;

    if (sigaction(SIGILL, &sa, NULL) != 0) {
        return PyErr_SetFromErrno(PyExc_SystemError);
    }

    if (sigaction(SIGFPE, &sa, NULL) != 0) {
        return PyErr_SetFromErrno(PyExc_SystemError);
    }

    if (sigaction(SIGSEGV, &sa, NULL) != 0) {
        return PyErr_SetFromErrno(PyExc_SystemError);
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doSetSystemTime(PyObject *s, PyObject  *args) {
    struct timeval tv;
    tv.tv_usec = 0;

    if (!PyArg_ParseTuple(args, "L", &(tv.tv_sec)))
        return NULL;

    if (settimeofday(&tv, NULL) != 0)
        return PyErr_SetFromErrno(PyExc_SystemError);

    Py_INCREF(Py_None);
    return Py_None;
}


/* vim:set shiftwidth=4 softtabstop=4: */

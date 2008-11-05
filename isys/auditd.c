/*
 * auditd.c
 *
 * This is a simple audit daemon that throws all messages away.
 *
 * Peter Jones <pjones@redhat.com>
 *
 * Copyright 2006 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License, version 2.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#define _GNU_SOURCE 1

#include <sys/types.h>
#include <sys/syscall.h>
#include <sys/poll.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

#include <libaudit.h>

#include "auditd.h"

#ifdef USESELINUX
static int done;

static void sig_done(int sig)
{
    done = 1;
}

static void do_auditd(int fd) {
    struct audit_reply rep;
    sigset_t sigs;
    struct sigaction sa;
    struct pollfd pds = {
        .events = POLLIN | POLLPRI | POLLERR | POLLHUP | POLLMSG,
        .revents = 0,
        .fd = fd,
    };

    if (audit_set_pid(fd, getpid(), WAIT_YES) < 0)
        return;

    if (audit_set_enabled(fd, 1) < 0)
        return;

    memset(&sa, '\0', sizeof (sa));
    sa.sa_handler = sig_done;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);

    sigfillset(&sigs);
    sigdelset(&sigs, SIGTERM);
    sigdelset(&sigs, SIGINT);
    sigdelset(&sigs, SIGHUP);

    while (1) {
        struct timespec timeout = { -1, -1 };
        int retval;

        memset(&rep, 0, sizeof(rep));

        do {
            retval = ppoll(&pds, 1, &timeout, &sigs);
        } while (retval == -1 && errno == EINTR && !done);

        if (done)
            break;

        if (audit_get_reply(fd, &rep, GET_REPLY_NONBLOCKING, 0) > 0) {
            /* we don't actually want to do anything here. */
            ;
        }
    }
    return;
}
#endif /* USESELINUX */

int audit_daemonize(void) {
#ifdef USESELINUX
    int fd;
#ifndef STANDALONE 
    int i;
    pid_t child;

    if ((child = fork()) > 0)
        return 0;

    for (i = 0; i < getdtablesize(); i++)
        close(i);

    signal(SIGTTOU, SIG_IGN);
    signal(SIGTTIN, SIG_IGN);
    signal(SIGTSTP, SIG_IGN);

    if ((fd = open("/proc/self/oom_adj", O_RDWR)) >= 0) {
        i = write(fd, "-17", 3);
        close(fd);
    }

#endif /* !defined(STANDALONE) */
    fd = audit_open();
    do_auditd(fd);
    audit_close(fd);
#endif /* USESELINUX */
    exit(0);
}

#ifdef STANDALONE
int main(void) {
    return audit_daemonize();
}
#endif /* STANDALONE */

/*
 * vim:ts=8:sw=4:sts=4:et
 */

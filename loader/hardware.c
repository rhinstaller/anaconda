/*
 * hardware.c - various hardware probing functionality
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
 * All rights reserved.
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
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>
#include <sys/wait.h>
#include <glib.h>

#include "loader.h"
#include "hardware.h"

/* FIXME: for turning off dma */
#include <sys/ioctl.h>
#include <linux/hdreg.h>
#include "../isys/isys.h"
#include "../isys/log.h"

/* boot flags */
extern uint64_t flags;

static int detectHardware() {
    int child, rc, status;
    int timeout = 0; /* FIXME: commandline option for this */

    fprintf(stderr, "detecting hardware...\n");
    logMessage(DEBUGLVL, "probing buses");

    if (!(child = fork())) {
        int fd = open("/dev/tty3", O_RDWR);

        dup2(fd, 0);
        dup2(fd, 1);
        dup2(fd, 2);
        close(fd);

        rc = execl("/sbin/udevadm", "udevadm", "trigger", NULL);
        _exit(1);
    }

    waitpid(child, &status, 0);
    if (!WIFEXITED(status) || (WIFEXITED(status) && WEXITSTATUS(status))) {
        rc = 1;
    } else {
        rc = 0;
    }

    fprintf(stderr, "waiting for hardware to initialize...\n");
    logMessage(DEBUGLVL, "waiting for hardware to initialize");

    if (!(child = fork())) {
        char *args[] = { "/sbin/udevadm", "settle", NULL, NULL };
        int fd = open("/dev/tty3", O_RDWR);

        dup2(fd, 0);
        dup2(fd, 1);
        dup2(fd, 2);
        close(fd);

        if (timeout) {
            checked_asprintf(&args[2], "--timeout=%d", timeout);
        }

        rc = execv("/sbin/udevadm", args);
        _exit(1);
    }

    waitpid(child, &status, 0);
    if (!WIFEXITED(status) || (WIFEXITED(status) && WEXITSTATUS(status))) {
        rc = 1;
    } else {
        rc = 0;
    }
    if (rc) {
        return LOADER_ERROR;
    }
    return LOADER_OK;
}

/* this allows us to do an early load of modules specified on the
 * command line to allow automating the load order of modules so that
 * eg, certain scsi controllers are definitely first.
 * FIXME: this syntax is likely to change in a future release
 *        but is done as a quick hack for the present.
 */
int earlyModuleLoad(int justProbe) {
    int fd, len, i;
    char buf[1024], *cmdLine;
    gint argc = 0;
    gchar **argv = NULL;
    GError *optErr = NULL;

    /* FIXME: reparsing /proc/cmdline to avoid major loader changes.  
     * should probably be done in loader.c:parseCmdline() like everything 
     * else
     */
    if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return 1;
    len = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (len <= 0) return 1;

    buf[len] = '\0';
    cmdLine = buf;

    if (!g_shell_parse_argv(cmdLine, &argc, &argv, &optErr)) {
        g_error_free(optErr);
        return 1;
    }

    for (i=0; i < argc; i++) {
        if (!strncasecmp(argv[i], "driverload=", 11)) {
            logMessage(INFO, "loading %s early", argv[i] + 11);
            mlLoadModuleSet(argv[i] + 11);
        }
    }
    return 0;
}

int busProbe(int justProbe) {
    /* autodetect whatever we can */
    if (justProbe)
        return 0;
    return detectHardware();
}

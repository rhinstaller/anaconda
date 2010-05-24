/*
 * loadermisc.c - miscellaneous loader functions that don't seem to fit
 * anywhere else (yet)  (was misc.c)
 * JKFIXME: need to break out into reasonable files based on function
 *
 * Copyright (C) 1999, 2000, 2001, 2002  Red Hat, Inc.  All rights reserved.
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

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdlib.h>

#include "../isys/log.h"

#include "windows.h"

int copyFileFd(int infd, char * dest, progressCB pbcb,
               struct progressCBdata *data, long long total) {
    int outfd;
    char buf[4096];
    int i;
    int rc = 0;
    long long count = 0;

    outfd = open(dest, O_CREAT | O_RDWR, 0666);

    if (outfd < 0) {
        logMessage(ERROR, "failed to open %s: %m", dest);
        return 1;
    }

    while ((i = read(infd, buf, sizeof(buf))) > 0) {
        if (write(outfd, buf, i) != i) {
            rc = 1;
            break;
        }

        count += i;

        if (pbcb && data && total) {
            pbcb(data, count, total);
        }
    }

    close(outfd);

    return rc;
}

int copyFile(char * source, char * dest) {
    int infd = -1;
    int rc;

    infd = open(source, O_RDONLY);

    if (infd < 0) {
        logMessage(ERROR, "failed to open %s: %m", source);
        return 1;
    }

    rc = copyFileFd(infd, dest, NULL, NULL, 0);

    close(infd);

    return rc;
}

int simpleStringCmp(const void * a, const void * b) {
    const char * first = *((const char **) a);
    const char * second = *((const char **) b);

    return strverscmp(first, second);
}

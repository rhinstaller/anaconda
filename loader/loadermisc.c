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
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>

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

/**
 * Do "rm -rf" on the target directory.
 *
 * Returns 0 on success, nonzero otherwise (i.e. directory doesn't exist or
 * some of its contents couldn't be removed.
 *
 * This is copied from the util-linux-ng project.
 */
int recursiveRemove(int fd)
{
    struct stat rb;
    DIR *dir;
    int rc = -1;
    int dfd;

    if (!(dir = fdopendir(fd))) {
        goto done;
    }

    /* fdopendir() precludes us from continuing to use the input fd */
    dfd = dirfd(dir);

    if (fstat(dfd, &rb)) {
        goto done;
    }

    while(1) {
        struct dirent *d;

        errno = 0;
        if (!(d = readdir(dir))) {
            if (errno) {
                goto done;
            }
            break;  /* end of directory */
        }

        if (!strcmp(d->d_name, ".") || !strcmp(d->d_name, ".."))
            continue;

        if (d->d_type == DT_DIR) {
            struct stat sb;

            if (fstatat(dfd, d->d_name, &sb, AT_SYMLINK_NOFOLLOW)) {
                continue;
            }

            /* remove subdirectories if device is same as dir */
            if (sb.st_dev == rb.st_dev) {
                int cfd;

                cfd = openat(dfd, d->d_name, O_RDONLY);
                if (cfd >= 0) {
                    recursiveRemove(cfd);
                    close(cfd);
                }
            } else
                continue;
        }

        unlinkat(dfd, d->d_name, d->d_type == DT_DIR ? AT_REMOVEDIR : 0);
    }

    rc = 0; /* success */

 done:
    if (dir)
        closedir(dir);
    return rc;
}

int simpleStringCmp(const void * a, const void * b) {
    const char * first = *((const char **) a);
    const char * second = *((const char **) b);

    return strverscmp(first, second);
}

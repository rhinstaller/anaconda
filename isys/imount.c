/*
 * imount.c
 *
 * Copyright (C) 2007, 2008 Red Hat, Inc.  All rights reserved.
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

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "imount.h"
#include "sundries.h"

#define _(foo) foo

static int mkdirIfNone(char * directory);

int doPwMount(char *dev, char *where, char *fs, char *options) {
    int rc, child, status;
    char *opts = NULL, *device;

    if (mkdirChain(where)) {
        return IMOUNT_ERR_ERRNO;
    }

    if (strstr(fs, "nfs")) {
        if (options)
            rc = asprintf(&opts, "%s,nolock", options);
        else
            opts = strdup("nolock");
        device = strdup(dev);
    } else {
        if ((options && strstr(options, "bind") == NULL) && 
            strncmp(dev, "LABEL=", 6) && strncmp(dev, "UUID=", 5) && *dev != '/')
           rc = asprintf(&device, "/dev/%s", dev);
        else
           device = strdup(dev);
        if (options)
            opts = strdup(options);
    }


    if (!(child = fork())) {
        int fd;

        /* Close off all these filehandles since we don't want errors
         * spewed to tty1.
         */
        fd = open("/dev/tty5", O_RDONLY);
        close(STDIN_FILENO);
        dup2(fd, STDIN_FILENO);
        close(fd);

        fd = open("/dev/tty5", O_WRONLY);
        close(STDOUT_FILENO);
        dup2(fd, STDOUT_FILENO);
        close(STDERR_FILENO);
        dup2(fd, STDERR_FILENO);
        close(fd);

        if (opts) {
            fprintf(stderr, "Running... /bin/mount -n -t %s -o %s %s %s\n",
                    fs, opts, device, where);
            rc = execl("/bin/mount",
                       "/bin/mount", "-n", "-t", fs, "-o", opts, device, where, NULL);
            exit(1);
        }
        else {
            fprintf(stderr, "Running... /bin/mount -n -t %s %s %s\n",
                    fs, device, where);
            rc = execl("/bin/mount", "/bin/mount", "-n", "-t", fs, device, where, NULL);
            exit(1);
        }
    }

    waitpid(child, &status, 0);

    free(opts);
    free(device);
    if (!WIFEXITED(status) || (WIFEXITED(status) && WEXITSTATUS(status)))
       return IMOUNT_ERR_OTHER;

    return 0;
}

int mkdirChain(char * origChain) {
    char * chain;
    char * chptr;

    chain = alloca(strlen(origChain) + 1);
    strcpy(chain, origChain);
    chptr = chain;

    while ((chptr = strchr(chptr, '/'))) {
	*chptr = '\0';
	if (mkdirIfNone(chain)) {
	    *chptr = '/';
	    return IMOUNT_ERR_ERRNO;
	}

	*chptr = '/';
	chptr++;
    }

    if (mkdirIfNone(chain))
	return IMOUNT_ERR_ERRNO;

    return 0;
}

static int mkdirIfNone(char * directory) {
    int rc, mkerr;
    char * chptr;

    /* If the file exists it *better* be a directory -- I'm not going to
       actually check or anything */
    if (!access(directory, X_OK)) return 0;

    /* if the path is '/' we get ENOFILE not found" from mkdir, rather
       then EEXIST which is weird */
    for (chptr = directory; *chptr; chptr++)
        if (*chptr != '/') break;
    if (!*chptr) return 0;

    rc = mkdir(directory, 0755);
    mkerr = errno;

    if (!rc || mkerr == EEXIST) return 0;

    return IMOUNT_ERR_ERRNO;
}

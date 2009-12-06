/*
 * imount.c
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

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "imount.h"

#define _(foo) foo

static int mkdirIfNone(char * directory);

static int readFD(int fd, char **buf) {
    char *p;
    size_t size = 4096;
    int s, filesize = 0;

    *buf = calloc(4096, sizeof (char));
    if (*buf == NULL)
        abort();

    do {
        p = &(*buf)[filesize];
        s = read(fd, p, 4096);
        if (s < 0)
            break;

        filesize += s;
        if (s == 0)
           break;

        size += s;
        *buf = realloc(*buf, size);
        if (*buf == NULL)
            abort();
    } while (1);

    if (filesize == 0 && s < 0) {
        free(*buf);
        *buf = NULL;
        return -1;
    }

    return filesize;
}

int mountCommandWrapper(int mode, char *dev, char *where, char *fs,
                        char *options, char **err) {
    int rc, child, status, pipefd[2];
    char *opts = NULL, *device = NULL, *cmd = NULL;
    int programLogFD;

    if (mode == IMOUNT_MODE_MOUNT) {
        cmd = "/bin/mount";
    } else if (mode == IMOUNT_MODE_UMOUNT) {
        cmd = "/bin/umount";
    } else {
        return IMOUNT_ERR_MODE;
    }

    if (mode == IMOUNT_MODE_MOUNT) {
        if (mkdirChain(where))
            return IMOUNT_ERR_ERRNO;

        if (strstr(fs, "nfs")) {
            if (options) {
                if (asprintf(&opts, "%s,nolock", options) == -1) {
                    fprintf(stderr, "%s: %d: %s\n", __func__, __LINE__,
                            strerror(errno));
                    fflush(stderr);
                    abort();
                }
            } else {
                opts = strdup("nolock");
            }

            device = strdup(dev);
        } else {
            if ((options && strstr(options, "bind") == NULL) &&
                strncmp(dev, "LABEL=", 6) && strncmp(dev, "UUID=", 5) &&
                *dev != '/') {
               if (asprintf(&device, "/dev/%s", dev) == -1) {
                   fprintf(stderr, "%s: %d: %s\n", __func__, __LINE__,
                           strerror(errno));
                   fflush(stderr);
                   abort();
               }
            } else {
               device = strdup(dev);
            }

            if (options)
                opts = strdup(options);
        }
    }

    programLogFD = open("/tmp/program.log",
                        O_APPEND|O_CREAT|O_WRONLY, S_IRUSR|S_IWUSR|S_IRGRP|S_IROTH);

    if (pipe(pipefd))
        return IMOUNT_ERR_ERRNO;

    if (!(child = fork())) {
        int fd;

        close(pipefd[0]);

        /* Close stdin entirely, redirect stdout to /tmp/program.log, and
         * redirect stderr to a pipe so we can put error messages into
         * exceptions.  We'll only use these messages should mount also
         * return an error code.
         */
        fd = open("/dev/tty5", O_RDONLY);
        close(STDIN_FILENO);
        dup2(fd, STDIN_FILENO);
        close(fd);

        close(STDOUT_FILENO);
        dup2(programLogFD, STDOUT_FILENO);

        dup2(pipefd[1], STDERR_FILENO);

        if (mode == IMOUNT_MODE_MOUNT) {
            if (opts) {
                fprintf(stdout, "Running... %s -n -t %s -o %s %s %s\n",
                        cmd, fs, opts, device, where);
                rc = execl(cmd, cmd,
                           "-n", "-t", fs, "-o", opts, device, where, NULL);
                exit(1);
            } else {
                fprintf(stdout, "Running... %s -n -t %s %s %s\n",
                        cmd, fs, device, where);
                rc = execl(cmd, cmd, "-n", "-t", fs, device, where, NULL);
                exit(1);
            }
        } else if (mode == IMOUNT_MODE_UMOUNT) {
            fprintf(stdout, "Running... %s %s\n", cmd, where);
            rc = execl(cmd, cmd, where, NULL);
            exit(1);
        } else {
            fprintf(stdout, "Running... Unknown imount mode: %d\n", mode);
            exit(1);
        }
    }

    close(pipefd[1]);

    if (err != NULL) {
        if (*err != NULL) {
            rc = readFD(pipefd[0], err);
            rc = write(programLogFD, *err, 4096);
        }
    }

    close(pipefd[0]);
    waitpid(child, &status, 0);

    close(programLogFD);

    if (opts) {
        free(opts);
    }

    if (device) {
        free(device);
    }

    if (!WIFEXITED(status))
        return IMOUNT_ERR_OTHER;
    else if ( (rc = WEXITSTATUS(status)) ) {
        /* Refer to 'man mount' for the meaning of the error codes. */
        switch (rc) {
        case 1:
            return IMOUNT_ERR_PERMISSIONS;
        case 2:
            return IMOUNT_ERR_SYSTEM;
        case 4:
            return IMOUNT_ERR_MOUNTINTERNAL;
        case 8:
            return IMOUNT_ERR_USERINTERRUPT;
        case 16:
            return IMOUNT_ERR_MTAB;
        case 32:
            return IMOUNT_ERR_MOUNTFAILURE;
        case 64:
            return IMOUNT_ERR_PARTIALSUCC;
        default:
            return IMOUNT_ERR_OTHER;
        }
    }

    return 0;
}

int doPwMount(char *dev, char *where, char *fs, char *options, char **err) {
    return mountCommandWrapper(IMOUNT_MODE_MOUNT,
                               dev, where, fs, options, err);
}

int doPwUmount(char *where, char **err) {
    return mountCommandWrapper(IMOUNT_MODE_UMOUNT,
                               NULL, where, NULL, NULL, err);
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

/* Returns true iff it is possible that the mount command that have returned
 * 'errno' might succeed at a later time (think e.g. not yet initialized USB
 * device, etc.) */
int mountMightSucceedLater(int mountRc)
{
    int rc;
    switch (mountRc) {
    case IMOUNT_ERR_MOUNTFAILURE:
        rc = 1;
        break;
    default:
        rc = 0;
    }
    return rc;
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

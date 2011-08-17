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
#include <glib.h>

#include "imount.h"
#include "log.h"

#define _(foo) foo

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

static size_t rstrip(char *str) {
    size_t len = strlen(str);
    if (len > 0 && str[len-1] == '\n') {
        str[len-1] = '\0';
        --len;
    }
    return len;
}

int mountCommandWrapper(int mode, char *dev, char *where, char *fs,
                        char *options, char **err) {
    int rc, child, status;
    int stdout_pipe[2], stderr_pipe[2];
    char *opts = NULL, *device = NULL, *cmd = NULL;

    switch (mode) {
    case IMOUNT_MODE_MOUNT:
    case IMOUNT_MODE_BIND:
        cmd = "/bin/mount";
        if (g_mkdir_with_parents(where, 0755))
            return IMOUNT_ERR_ERRNO;
        break;
    case IMOUNT_MODE_UMOUNT:
        cmd = "/bin/umount";
        break;
    default:
        return IMOUNT_ERR_MODE;
    }

    if (mode == IMOUNT_MODE_MOUNT) {
        if (strstr(fs, "nfs")) {
            if (options && strlen(options)) { // do not append if the options are empty
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

    if (pipe(stdout_pipe))
        return IMOUNT_ERR_ERRNO;
    if (pipe(stderr_pipe))
        return IMOUNT_ERR_ERRNO;

    if (!(child = fork())) {
        int tty_fd;

        close(stdout_pipe[0]);
        close(stderr_pipe[0]);

        /* Pull stdin from /dev/tty5 and redirect stdout and stderr to the pipes
         *  so we can log the output and put error messages into exceptions.
         *  We'll only use these messages should mount also return an error
         *  code.
         */
        tty_fd = open("/dev/tty5", O_RDONLY);
        close(STDIN_FILENO);
        dup2(tty_fd, STDIN_FILENO);
        close(tty_fd);

        close(STDOUT_FILENO);
        dup2(stdout_pipe[1], STDOUT_FILENO);
        close(STDERR_FILENO);
        dup2(stderr_pipe[1], STDERR_FILENO);

        if (mode == IMOUNT_MODE_MOUNT) {
            if (opts) {
                logProgramMessage(INFO, "Running... %s -n -t %s -o %s %s %s",
                        cmd, fs, opts, device, where);
                rc = execl(cmd, cmd,
                           "-n", "-t", fs, "-o", opts, device, where, NULL);
                exit(1);
            } else {
                logProgramMessage(INFO, "Running... %s -n -t %s %s %s",
                        cmd, fs, device, where);
                rc = execl(cmd, cmd, "-n", "-t", fs, device, where, NULL);
                exit(1);
            }
        } else if (mode == IMOUNT_MODE_BIND) {
            logProgramMessage(INFO, "Running... %s --bind %s %s",
                              cmd, dev, where);
            rc = execl(cmd, cmd, "--bind", dev, where, NULL);
            exit(1);
        } else if (mode == IMOUNT_MODE_UMOUNT) {
            logProgramMessage(INFO, "Running... %s %s", cmd, where);
            rc = execl(cmd, cmd, where, NULL);
            exit(1);
        } else {
            logProgramMessage(ERROR, "Running... Unknown imount mode: %d\n", mode);
            exit(1);
        }
    }

    close(stdout_pipe[1]);
    close(stderr_pipe[1]);

    char *buffer = NULL;
    /* In case when when the stderr pipe gets enough data to fill the kernel
     * buffer we might see a deadlock as this will block the mount program on
     * its next write(). The buffer size is 65kB though so we should be safe.
     */
    rc = readFD(stdout_pipe[0], &buffer);
    if (rc > 0) {
        rstrip(buffer);
        logProgramMessage(INFO, buffer);
        free(buffer);
        buffer = NULL;
    }
    rc = readFD(stderr_pipe[0], &buffer);
    if (rc > 0) {
        rstrip(buffer);
        logProgramMessage(ERROR, buffer);
        if (err != NULL)
            *err = buffer;
        else
            free(buffer);
    }

    waitpid(child, &status, 0);
    close(stdout_pipe[0]);
    close(stderr_pipe[0]);

    if (opts) {
        free(opts);
    }

    if (device) {
        free(device);
    }

    if (!WIFEXITED(status))
        return IMOUNT_ERR_OTHER;
    else if ( (rc = WEXITSTATUS(status)) )
        return rc;

    return 0;
}

int doBindMount(char* path, char *where, char **err) {
    return mountCommandWrapper(IMOUNT_MODE_BIND,
                               path, where, NULL, NULL, err);
}

int doPwMount(char *dev, char *where, char *fs, char *options, char **err) {
    return mountCommandWrapper(IMOUNT_MODE_MOUNT,
                               dev, where, fs, options, err);
}

int doPwUmount(char *where, char **err) {
    return mountCommandWrapper(IMOUNT_MODE_UMOUNT,
                               NULL, where, NULL, NULL, err);
}

/* Returns true iff it is possible that the mount command that have returned
 * 'errno' might succeed at a later time (think e.g. not yet initialized USB
 * device, etc.) */
int mountMightSucceedLater(int mountRc)
{
    /* 32 is the mount exit code for "mount failure" */
    if (mountRc > 0 && mountRc & 0x20)
        return 1;
    else
        return 0;
}

/*
 * copy.c - functions for copying files and directories
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "lang.h"

/* Recursive */
int copyDirectory(char * from, char * to, void (*warnFn)(char *),
                  void (*errorFn)(char *)) {
    char *msg;
    DIR * dir;
    struct dirent * ent;
    int fd, outfd;
    char buf[4096];
    int i;
    struct stat sb;
    char filespec[256];
    char filespec2[256];
    char link[1024];

    mkdir(to, 0755);

    if (!(dir = opendir(from))) {
        if (errorFn) {
           if (asprintf(&msg, N_("Failed to read directory %s: %m"), from) == -1) {
               fprintf(stderr, "%s: %d: %m\n", __func__, __LINE__);
               fflush(stderr);
               abort();
           }

           errorFn(msg);
           free(msg);
        }

        return 1;
    }

    errno = 0;
    while ((ent = readdir(dir))) {
        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, ".."))
           continue;

        sprintf(filespec, "%s/%s", from, ent->d_name);
        sprintf(filespec2, "%s/%s", to, ent->d_name);

        lstat(filespec, &sb);

        if (S_ISDIR(sb.st_mode)) {
            if (copyDirectory(filespec, filespec2, warnFn, errorFn)) {
                closedir(dir);
                return 1;
            }
        } else if (S_ISLNK(sb.st_mode)) {
            i = readlink(filespec, link, sizeof(link) - 1);
            link[i] = '\0';
            if (symlink(link, filespec2)) {
                if (warnFn) {
                    if (asprintf(&msg, "Failed to symlink %s to %s: %m",
                                 filespec2, link) == -1) {
                        fprintf(stderr, "%s: %d: %m\n", __func__, __LINE__);
                        fflush(stderr);
                        abort();
                    }

                    warnFn(msg);
                    free(msg);
                }
            }
        } else {
            fd = open(filespec, O_RDONLY);
            if (fd == -1) {
                if (errorFn) {
                    if (asprintf(&msg, "Failed to open %s: %m", filespec) == -1) {
                        fprintf(stderr, "%s: %d: %m\n", __func__, __LINE__);
                        fflush(stderr);
                        abort();
                    }

                    errorFn(msg);
                    free(msg);
                }

                closedir(dir);
                return 1;
            } 
            outfd = open(filespec2, O_RDWR | O_TRUNC | O_CREAT, 0644);
            if (outfd == -1) {
                if (warnFn) {
                    if (asprintf(&msg, "Failed to create %s: %m", filespec2) == -1) {
                        fprintf(stderr, "%s: %d: %m\n", __func__, __LINE__);
                        fflush(stderr);
                        abort();
                    }

                    warnFn(msg);
                    free(msg);
                }
            } else {
                fchmod(outfd, sb.st_mode & 07777);

                while ((i = read(fd, buf, sizeof(buf))) > 0)
                    i = write(outfd, buf, i);
                close(outfd);
            }

            close(fd);
        }

        errno = 0;
    }

    closedir(dir);

    return 0;
}

/*
 * devices.c - various hardware probing functionality
 *
 * Copyright (C) 2007  Red Hat, Inc.
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
 * Author(s): Bill Nottingham <notting@redhat.com>
 */

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <limits.h>
#include <net/if_arp.h>

#include "devices.h"

/* for 'disks', to filter out weird stuff */
#define MINIMUM_INTERESTING_SIZE	32*1024 	/* 32MB */

/* from genhd.h, kernel side */
#define GENHD_FL_REMOVABLE                      1
#define GENHD_FL_DRIVERFS                       2
#define GENHD_FL_MEDIA_CHANGE_NOTIFY            4
#define GENHD_FL_CD                             8
#define GENHD_FL_UP                             16
#define GENHD_FL_SUPPRESS_PARTITION_INFO        32
#define GENHD_FL_FAIL                           64


struct device **getDevices(enum deviceType type) {
    struct device **ret = NULL;
    struct device *new;
    int numdevices = 0;

    if (type & (DEVICE_DISK | DEVICE_CDROM)) {
        DIR *dir;
        struct dirent *ent;

        dir = opendir("/sys/block");

        if (!dir) goto storagedone;

        while ((ent = readdir(dir))) {
            char path[64];
            char buf[64];
            int fd, caps, devtype;

            snprintf(path, 64, "/sys/block/%s/capability", ent->d_name);
            fd = open(path, O_RDONLY);
            if (fd == -1)
                continue;
            if (read(fd, buf, 63) <= 0) {
                close(fd);
                continue;
            }

            close(fd);
            errno = 0;
            caps = strtol(buf, NULL, 16);

            if ((errno == ERANGE && (caps == LONG_MIN || caps == LONG_MAX)) ||
                (errno != 0 && caps == 0)) {
                return NULL;
            }

            if (caps & GENHD_FL_CD)
                devtype = DEVICE_CDROM;
            else
                devtype = DEVICE_DISK;
            if (!(devtype & type))
                continue;

            if (devtype == DEVICE_DISK && !(caps & GENHD_FL_REMOVABLE)) {
                long long int size;

                snprintf(path, 64, "/sys/block/%s/size", ent->d_name);
                fd = open(path, O_RDONLY);

                if (fd == -1)
                    continue;
                if (read(fd, buf, 63) <= 0) {
                    close(fd);
                    continue;
                }

                close(fd);
                errno = 0;
                size = strtoll(buf, NULL, 10);

                if ((errno == ERANGE && (size == LLONG_MIN ||
                                         size == LLONG_MAX)) ||
                    (errno != 0 && size == 0)) {
                    return NULL;
                }

                if (size < MINIMUM_INTERESTING_SIZE)
                    continue;
            }

            new = calloc(1, sizeof(struct device));
            new->device = strdup(ent->d_name);
            /* FIXME */
            if (asprintf(&new->description, "Storage device %s",
                         new->device) == -1) {
                fprintf(stderr, "%s: %d: %s\n", __func__, __LINE__,
                        strerror(errno));
                fflush(stderr);
                abort();
            }
            new->type = devtype;
            if (caps & GENHD_FL_REMOVABLE) {
                new->priv.removable = 1;
            }
            ret = realloc(ret, (numdevices+2) * sizeof(struct device));
            ret[numdevices] = new;
            ret[numdevices+1] = NULL;
            numdevices++;
        }

        closedir(dir);
    }
storagedone:

    if (type & DEVICE_NETWORK) {
        DIR *dir;
        struct dirent *ent;

        dir = opendir("/sys/class/net");

        if (!dir) goto netdone;

        while ((ent = readdir(dir))) {
            char path[64];
            int fd, type;
            char buf[64];

            snprintf(path, 64, "/sys/class/net/%s/type", ent->d_name);
            fd = open(path, O_RDONLY);
            if (fd == -1)
                continue;
            if (read(fd, buf, 63) <= 0) {
                close(fd);
                continue;
            }

            close(fd);
            errno = 0;
            type = strtol(buf, NULL, 10);

            if ((errno == ERANGE && (type == LONG_MIN || type == LONG_MAX)) ||
                (errno != 0 && type == 0)) {
                return NULL;
            }

            /* S390 channel-to-channnel devices have type 256 */
            if ((type != ARPHRD_ETHER) &&
                !((type == ARPHRD_SLIP) && !strncmp(ent->d_name, "ctc", 3)))
                continue;

            new = calloc(1, sizeof(struct device));
            new->device = strdup(ent->d_name);
            /* FIXME */
            snprintf(path, 64, "/sys/class/net/%s/address", ent->d_name);
            fd = open(path, O_RDONLY);
            if (fd != -1) {
                memset(buf, '\0', 64);
                if (read(fd, buf, 63) > 0) {
                    int i;
                    for (i = (strlen(buf)-1); isspace(buf[i]); i--)
                        buf[i] = '\0';
                    new->priv.hwaddr = strdup(buf);
                }
                close(fd);
            }

            if (new->priv.hwaddr) {
                if (asprintf(&new->description, "Ethernet device %s - %s",
                             new->device, new->priv.hwaddr) == -1) {
                    fprintf(stderr, "%s: %d: %s\n", __func__, __LINE__,
                            strerror(errno));
                    fflush(stderr);
                    abort();
                }
            } else {
                if (asprintf(&new->description, "Ethernet device %s",
                             new->device) == -1) {
                    fprintf(stderr, "%s: %d: %s\n", __func__, __LINE__,
                            strerror(errno));
                    fflush(stderr);
                    abort();
                }
            }

            ret = realloc(ret, (numdevices+2) * sizeof(struct device));
            ret[numdevices] = new;
            ret[numdevices+1] = NULL;
            numdevices++;
        }

        closedir(dir);
    }
netdone:
    return ret;
}


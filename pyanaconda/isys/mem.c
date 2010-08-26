/*
 * mem.c - memory checking
 *
 * Copyright (C) 2010
 * Red Hat, Inc.  All rights reserved.
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

#include <ctype.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "mem.h"
#include "log.h"

/* look for available memory.  note: won't ever report more than the 
 * 900 megs or so supported by the -BOOT kernel due to not using e820 */
int totalMemory(void) {
    int fd;
    int bytesRead;
    char buf[4096];
    char * chptr, * start;
    int total = 0;

    fd = open("/proc/meminfo", O_RDONLY);
    if (fd < 0) {
        logMessage(ERROR, "failed to open /proc/meminfo: %m");
        return 0;
    }

    bytesRead = read(fd, buf, sizeof(buf) - 1);
    if (bytesRead < 0) {
        logMessage(ERROR, "failed to read from /proc/meminfo: %m");
        close(fd);
        return 0;
    }

    close(fd);
    buf[bytesRead] = '\0';

    chptr = buf;
    while (*chptr && !total) {
        if (strncmp(chptr, "MemTotal:", 9)) {
            chptr++;
            continue;
        }

        start = ++chptr ;
        while (*chptr && *chptr != '\n') chptr++;

        *chptr = '\0';

        while (!isdigit(*start) && *start) start++;
        if (!*start) {
            logMessage(WARNING, "no number appears after MemTotal tag");
            return 0;
        }

        chptr = start;
        while (*chptr && isdigit(*chptr)) {
            total = (total * 10) + (*chptr - '0');
            chptr++;
        }
    }

    /*Because /proc/meminfo only gives us the MemTotal (total physical RAM minus
    the kernel binary code), we need to round this up. Assuming every machine
    has the total RAM MB number divisible by 128. */
    total /= 1024;
    total = (total / 128 + 1) * 128;
    total *= 1024;

    logMessage(INFO, "%d kB (%d MB) are available", total, total / 1024);

    return total;
}


/* vim:set shiftwidth=4 softtabstop=4: */

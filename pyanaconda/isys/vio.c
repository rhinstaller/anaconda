/*
 * vio.c - probing for vio devices on the iSeries (viocd and viodasd)
 *
 * Copyright (C) 2003  Red Hat, Inc.  All rights reserved.
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
 * Author(s): Jeremy Katz <katzj@redhat.com>
 */

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if defined(__powerpc__)
static int readFD (int fd, char **buf)
{
    char *p;
    size_t size = 4096;
    int s, filesize;

    *buf = malloc (size);
    if (*buf == 0)
	return -1;

    filesize = 0;
    do {
	p = &(*buf) [filesize];
	s = read (fd, p, 4096);
	if (s < 0)
	    break;
	filesize += s;
	if (s == 0)
	    break;
	size += 4096;
	*buf = realloc (*buf, size);
    } while (1);

    if (filesize == 0 && s < 0) {
	free (*buf);
	*buf = NULL;
	return -1;
    }

    return filesize;
}
#endif

int isVioConsole(void) {
#if !defined(__powerpc__)
    return 0;
#else
    int fd, i;
    char *buf, *start;
    char driver[50], device[50];
    static int isviocons = -1;

    if (isviocons != -1)
	return isviocons;
    
    fd = open("/proc/tty/drivers", O_RDONLY);
    if (fd < 0) {
	fprintf(stderr, "failed to open /proc/tty/drivers!\n");
	return 0;
    }
    i = readFD(fd, &buf);
    if (i < 1) {
        close(fd);
	fprintf(stderr, "error reading /proc/tty/drivers!\n");
        return 0;
    }
    close(fd);
    buf[i] = '\0';

    isviocons = 0;
    start = buf;
    while (start && *start) {
	if (sscanf(start, "%s %s", (char *) &driver, (char *) &device) == 2) {
	    if (!strcmp(driver, "vioconsole") && !strcmp(device, "/dev/tty")) {
		isviocons = 1;
		break;
	    }
	}		
        start = strchr(start, '\n');
        if (start)
	    start++;
    }
    free(buf);
    return isviocons;
#endif
}

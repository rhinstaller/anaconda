/*
 * vio.c - probing for vio devices on the iSeries (viocd and viodasd)
 *
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2003  Red Hat, Inc.
 *
 */

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <kudzu/kudzu.h>

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

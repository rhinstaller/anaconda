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
#include "probe.h"

int vioGetCdDevs(struct knownDevices * devices) {
#if !defined(__powerpc__)
    return 0;
#else
    int fd, i;
    char * buf, * start, * end, * chptr, * next, * model, * ptr;
    int ctlNum = 0;
    char ctl[64];
    struct kddevice newDevice;

    if (access("/proc/iSeries/viocd", R_OK))
	return 0;

    /* Read from /proc/iSeries/viocd */
    fd = open("/proc/iSeries/viocd", O_RDONLY);
    if (fd < 0) {
	fprintf(stderr, "failed to open /proc/iSeries/viocd!\n");
	return 1;
    }

    i = readFD(fd, &buf);
    if (i < 1) {
        close(fd);
	fprintf(stderr, "error reading /proc/iSeries/viocd!\n");
        return 1;
    }
    close(fd);
    buf[i] = '\0';

    start = buf;
    end = start + strlen(start);
    while (*start && start < end) {
	/* parse till end of line and store the start of next line. */
	chptr = start;
	while (*chptr != '\n') chptr++;
	*chptr = '\0';
	next = chptr + 1;

	/* get rid of anything which is not alpha */
	while (!(isalpha(*start))) start++;

	model = NULL;
	if (!strncmp("viocd", start, 5))
	    model = "IBM Virtual CDROM";

	if (model) {
	    start += 13;
	    ptr = strchr(start, ' ');
	    *ptr++ = '\0';
	    
	    ctlNum = atoi(start);

	    chptr = strstr(ptr, "type ") + 5;
	    ptr = strchr(chptr, ',');
	    *ptr = '\0';

	    model = alloca((20 + strlen(chptr)) * sizeof(char *));
	    sprintf(model, "IBM Virtual CD-ROM Model %s", chptr);
	    snprintf(ctl, 63, "iseries/vcd%c", ctlNum + 'a');

	    if (!deviceKnown(devices, ctl)) {
	      newDevice.name = strdup(ctl);
	      newDevice.model = strdup(model);
	      newDevice.class = CLASS_CDROM;
	      addDevice(devices, newDevice);
	    }
	    //	    printf("model is %s, ctl is %s\n", model, ctl);
	}

	start = next;
	end = start + strlen(start);
    } /* end of while */

    free (buf);
    return 0;
#endif
}

int vioGetDasdDevs(struct knownDevices * devices) {
#if !defined(__powerpc__)
    return 0;
#else
    int fd, i;
    char * buf, * start, * end, * chptr, * next, * model, * ptr;
    int ctlNum = 0;
    char ctl[64];
    struct kddevice newDevice;

    if (access("/proc/iSeries/viodasd", R_OK))
	return 0;

    /* Read from /proc/iSeries/viodasd */
    fd = open("/proc/iSeries/viodasd", O_RDONLY);
    if (fd < 0) {
	fprintf(stderr, "failed to open /proc/iSeries/viodasd!\n");
	return 1;
    }

    i = readFD(fd, &buf);
    if (i < 1) {
        close(fd);
	fprintf(stderr, "error reading /proc/iSeries/viodasd!\n");
        return 1;
    }
    close(fd);
    buf[i] = '\0';

    start = buf;
    end = start + strlen(start);
    while (*start && start < end) {
	/* parse till end of line and store the start of next line. */
	chptr = start;
	while (*chptr != '\n') chptr++;
	*chptr = '\0';
	next = chptr + 1;

	/* get rid of anything which is not alpha */
	while (!(isalpha(*start))) start++;

	model = NULL;
	if (!strncmp("DISK ", start, 5))
	    model = "IBM Virtual DASD";

	if (model) {
	    chptr = start += 5;
	    ptr = strchr(chptr, ' ');
	    *ptr = '\0';
	    ctlNum = atoi(chptr);

	    if (ctlNum <= 26) {
		snprintf(ctl, 63, "iseries/vd%c", 'a' + ctlNum);
	    } else {
		snprintf(ctl, 63, "iseries/vda%c", 'a' + ctlNum - 26);
	    }
	   
	    if (!deviceKnown(devices, ctl)) {
	      newDevice.name = strdup(ctl);
	      newDevice.model = strdup(model);
	      newDevice.class = CLASS_HD;
	      addDevice(devices, newDevice);
	    }
	    //	    printf("model is %s, ctl is %s\n", model, ctl);
	}

	start = next;
	end = start + strlen(start);
    } /* end of while */

    free (buf);
    return 0;
#endif
}

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

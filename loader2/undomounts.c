/*
 * undomounts.c
 *
 * Handles some basic unmounting stuff for init
 * Broken out so that it can be used on s390 in a shutdown binary 
 *
 * Erik Troan <ewt@redhat.com>
 * Jeremy Katz <katzj@redhat.com> 
 *
 * Copyright 1996 - 2003 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <unistd.h>

#include "devt.h"

struct unmountInfo {
    char * name;
    int mounted;
    int loopDevice;
    enum { FS, LOOP } what;
} ;

extern int testing;

void undoLoop(struct unmountInfo * fs, int numFs, int this);

static void printstr(char * string) {
    int ret;
    
    ret = write(1, string, strlen(string));
}

void undoMount(struct unmountInfo * fs, int numFs, int this) {
    size_t len = strlen(fs[this].name);
    int i;

    if (!fs[this].mounted) return;
    fs[this].mounted = 0;

    /* unmount everything underneath this */
    for (i = 0; i < numFs; i++) {
	if (fs[i].name && (strlen(fs[i].name) >= len) &&
	    (fs[i].name[len] == '/') && 
	    !strncmp(fs[this].name, fs[i].name, len)) {
	    if (fs[i].what == LOOP)
		undoLoop(fs, numFs, i);
	    else
		undoMount(fs, numFs, i);
	} 
    }

    printf("\t%s", fs[this].name);
    /* don't need to unmount /tmp.  it is busy anyway. */
    if (!testing) {
	if (umount2(fs[this].name, 0) < 0) {
	    printf(" umount failed (%d)", errno);
	} else {
	    printf(" done");
	}
    }
    printf("\n");
}

void undoLoop(struct unmountInfo * fs, int numFs, int this) {
    int i;
    int fd;

    if (!fs[this].mounted) return;
    fs[this].mounted = 0;

    /* find the device mount */
    for (i = 0; i < numFs; i++) {
	if (fs[i].what == FS && (fs[i].loopDevice == fs[this].loopDevice))
	    break;
    }

    if (i < numFs) {
	/* the device is mounted, unmount it (and recursively, anything
	 * underneath) */
	undoMount(fs, numFs, i);
    }

    unlink("/tmp/loop");
    mknod("/tmp/loop", 0600 | S_IFBLK, (7 << 8) | fs[this].loopDevice);
    printf("\tdisabling /dev/loop%d", fs[this].loopDevice);
    if ((fd = open("/tmp/loop", O_RDONLY, 0)) < 0) {
	printf(" failed to open device: %d", errno);
    } else {
	if (!testing && ioctl(fd, LOOP_CLR_FD, 0))
	    printf(" LOOP_CLR_FD failed: %d", errno);
	close(fd);
    }

    printf("\n");
}

void unmountFilesystems(void) {
    int fd, size;
    char buf[65535];			/* this should be big enough */
    char * chptr, * start;
    struct unmountInfo filesystems[500];
    int numFilesystems = 0;
    int i;
    struct loop_info li;
    char * device;
    struct stat sb;

    fd = open("/proc/mounts", O_RDONLY, 0);
    if (fd < 1) {
	/* FIXME: was perror */
	printstr("failed to open /proc/mounts");
	sleep(2);
	return;
    }

    size = read(fd, buf, sizeof(buf) - 1);
    buf[size] = '\0';

    close(fd);

    chptr = buf;
    while (*chptr) {
	device = chptr;
	while (*chptr != ' ') chptr++;
	*chptr++ = '\0';
	start = chptr;
	while (*chptr != ' ') chptr++;
	*chptr++ = '\0';

	if (strcmp(start, "/") && strcmp(start, "/tmp") && 
            strcmp(start, "/dev")) {
	    filesystems[numFilesystems].name = strdup(start);
	    filesystems[numFilesystems].what = FS;
	    filesystems[numFilesystems].mounted = 1;

	    stat(start, &sb);
	    if ((sb.st_dev >> 8) == 7) {
		filesystems[numFilesystems].loopDevice = sb.st_dev & 0xf;
	    } else {
		filesystems[numFilesystems].loopDevice = -1;
	    }

	    numFilesystems++;
	}

	while (*chptr != '\n') chptr++;
	chptr++;
    }

    for (i = 0; i < 7; i++) {
	unlink("/tmp/loop");
	mknod("/tmp/loop", 0600 | S_IFBLK, (7 << 8) | i);
	if ((fd = open("/tmp/loop", O_RDONLY, 0)) >= 0) {
	    if (!ioctl(fd, LOOP_GET_STATUS, &li) && li.lo_name[0]) {
		filesystems[numFilesystems].name = strdup(li.lo_name);
		filesystems[numFilesystems].what = LOOP;
		filesystems[numFilesystems].mounted = 1;
		filesystems[numFilesystems].loopDevice = i;
		numFilesystems++;
	    }

	    close(fd);
	}
    }

    for (i = 0; i < numFilesystems; i++) {
	if (filesystems[i].what == LOOP) {
	    undoLoop(filesystems, numFilesystems, i);
	}
    }

    for (i = 0; i < numFilesystems; i++) {
	if ((filesystems[i].mounted) && (filesystems[i].name)) {
	    undoMount(filesystems, numFilesystems, i);
	}
    }

    for (i = 0; i < numFilesystems; i++) 
        free(filesystems[i].name);
}

void disableSwap(void) {
    int fd;
    char buf[4096];
    int i;
    char * start;
    char * chptr;

    if ((fd = open("/proc/swaps", O_RDONLY, 0)) < 0) return;

    i = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (i < 0) return;
    buf[i] = '\0';

    start = buf;
    while (*start) {
	while (*start != '\n' && *start) start++;
	if (!*start) return;

	start++;
	if (*start != '/') return;
	chptr = start;
	while (*chptr && *chptr != ' ') chptr++;
	if (!(*chptr)) return;
	*chptr = '\0';
	printf("\t%s", start);
	if (swapoff(start)) 
	    printf(" failed (%d)", errno);
	printf("\n");

	start = chptr + 1;
    }
}

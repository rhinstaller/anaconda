#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <asm/page.h>
#include <sys/swap.h>
#include <sys/sysmacros.h>
#include <sys/statfs.h>
#include <unistd.h>
#include <zlib.h>

#include "../isys/imount.h"
#include "../isys/isys.h"

#include "commands.h"
#include "mount_by_label.h"
#include "../isys/cpio.h"

static int copyfd(int to, int from);

static int copyfd(int to, int from) {
    char buf[1024];
    int size;

    while ((size = read(from, buf, sizeof(buf))) > 0) {
	if (write(to, buf, size) != size) {
	    fprintf(stderr, "error writing output: %s\n", strerror(errno));
	    return 1;
	}
    }

    if (size < 0) {
	fprintf(stderr, "error reading input: %s\n", strerror(errno));
	return 1;
    }

    return 0;
}

static int catFile(char * filename) {
    int fd;
    int rc;

    fd = open(filename, O_RDONLY);
    if (fd < 0) {
	fprintf(stderr, "cannot open %s: %s\n", filename, strerror(errno));
	return 1;
    }

    rc = copyfd(1, fd);
    close(fd);

    return rc;
}

#define MOUNT_USAGE fprintf(stderr, "usage: mount -t <fs> <device> <dir>\n" \
			"       (if /dev/ is left off the device name, a " \
			"temporary node will be created)\n")

int mountCommand(int argc, char ** argv) {
    char * dev, * dir;
    char * fs, * buf;

    if (argc < 2) {
	return catFile("/proc/mounts");
    } else if (argc == 3) {
	if (strchr(argv[1], ':'))
	    fs = "nfs";
	else
	    fs = "ext2";
	dev = argv[1];
	dir = argv[2];
    } else if (argc != 5) {
	MOUNT_USAGE;
	return 1;
    } else {
	if (strcmp(argv[1], "-t")) {
	    MOUNT_USAGE;
	    return 1;
	}
	
	fs = argv[2];
	dev = argv[3];
	dir = argv[4];
    }

    if (!strncmp(dev, "LABEL=", 6)) {
	dev = get_spec_by_volume_label(dev + 6);
    } else if (!strncmp(dev, "UUID=", 5)) {
	dev = get_spec_by_uuid(dev + 5);
    }

    if (!strncmp(dev, "/dev/", 5) && access(dev, X_OK)) {
	dev += 5;
	buf = alloca(strlen(dev) + 10);
	sprintf(buf, "/tmp/%s", dev);
	devMakeInode(dev, buf);
	dev = buf;
    }

    if (doPwMount(dev, dir, fs, 0, 1, NULL, NULL)) {
	if (doPwMount(dev, dir, fs, 1, 1, NULL, NULL)) {
	    fprintf(stderr, "mount failed: %s\n", strerror(errno));
	    return 1;
	}
    }

    return 0;
}

int umountCommand(int argc, char ** argv) {
    if (argc != 2) {
	fprintf(stderr, "umount expects a single argument\n");
	return 1;
    }

    if (umount(argv[1])) {
	fprintf(stderr, "error unmounting %s: %s\n", argv[1], strerror(errno));
	return 1;
    }

    return 0;
}

int mknodCommand(int argc, char ** argv) {
    int major, minor;
    char * path;
    int mode = 0600;
    char *end;

    if (argc != 5 && argc != 2) {
	fprintf(stderr, "usage: mknod <path> [b|c] <major> <minor> or mknod <path>\n");
	return 1;
    }

    path = argv[1];

    if (argc == 2) {
	end = path + strlen(path) - 1;
	while (end > path && *end != '/') end--;
	if (*end == '/') end++;

	if (devMakeInode(end, path)) {
	    printf("failed to make inode for device %s\n", end);
	    return 1;
	}

	return 0;
    }

    if (!strcmp(argv[2], "b")) 
	mode |= S_IFBLK;
    else if (!strcmp(argv[2], "c"))
	mode |= S_IFCHR;
    else {
	fprintf(stderr, "unknown node type %s\n", argv[2]);
	return 1;
    } 

    major = strtol(argv[3], &end, 0);
    if (*end) {
	fprintf(stderr, "bad major number %s\n", argv[3]);
	return 1;
    }

    minor = strtol(argv[4], &end, 0);
    if (*end) {
	fprintf(stderr, "bad minor number %s\n", argv[4]);
	return 1;
    }

    if (mknod(path, mode, makedev(major, minor))) {
	fprintf(stderr, "mknod failed: %s\n", strerror(errno));
	return 1;
    }

    return 0;
}

int uncpioCommand(int argc, char ** argv) {
    int rc;
    const char * fail;
    gzFile cfd;

    if (argc != 1) {
	fprintf(stderr, "uncpio reads from stdin");
	return 1;
    }

    cfd = gzdopen(0, "r");

    rc = myCpioInstallArchive(cfd, NULL, 0, NULL, NULL, &fail);

    if (rc) {
	fprintf(stderr, "cpio failed on %s: ", fail);
	if (rc & CPIOERR_CHECK_ERRNO)
	    fprintf(stderr, "%s\n", strerror(errno));
 	else
	    fprintf(stderr, "(internal)\n");
    }

    return (rc != 0);
}

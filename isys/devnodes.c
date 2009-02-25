/*
 * devnodes.c - device inode creation functions
 * 
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Peter Jones <pjones@redhat.com>
 *
 * Copyright 1998-2005 Red Hat, Inc.
 * Copyright 1996-1998 Red Hat Software, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <stdlib.h>
#include <limits.h>
#include <unistd.h>
#include <ctype.h>
#include <string.h>
#include <libdevmapper.h>

struct devnum {
    char * name;
    short major, minor;
    int isChar;
};

static struct devnum devices[] = {
    { "aztcd",		29,	0,	0 },
    { "pcd",		46,	0,	0 },
    { "cdu31a",		15,	0,	0 },
    { "cdu535",		24,	0,	0 },
    { "cm206cd",	32,	0,	0 },
    { "fd0",     	2,	0,	0 },
    { "fd1",		2,	1,	0 },
    { "gscd",		16,	0,	0 },
    { "input/mouse0",	13,	32,	1 },
    { "input/mouse1",	13,	33,	1 },
    { "input/mouse2",	13,	34,	1 },
    { "input/mouse3",	13,	35,	1 },
    { "input/event0",	13,	64,	1 },
    { "input/event1",	13,	65,	1 },
    { "input/event2",	13,	66,	1 },
    { "input/event3",	13,	67,	1 },
    { "lp0",		6,	0,	1 },
    { "lp1",		6,	1,	1 },
    { "lp2",		6,	2,	1 },
    { "mcd",		23,	0,	0 },
    { "mcdx",		20,	0,	0 },
    { "optcd",		17,	0,	0 },
    { "psaux",		10,	1,	1 },
    { "sbpcd",		25,	0,	0 },
    { "sjcd",		18,	0,	0 },
    { "ttyS0",		4,	64,	1 },
    { "ttyS1",		4,	65,	1 },
    { "ttyS2",		4,	66,	1 },
    { "ttyS3",		4,	67,	1 },
};

int idemajors[] = { 3, 22, 33, 34, 56, 57, 88, 89, 90, 91 };

int numDevices = sizeof(devices) / sizeof(struct devnum);

#include <linux/major.h>
/* from linux/drivers/scsi/sd.c */
static int sd_major(int major_idx) {
    switch (major_idx) {
    case 0:
        return SCSI_DISK0_MAJOR;
    case 1 ... 7:
        return SCSI_DISK1_MAJOR + major_idx - 1;
    case 8 ... 15:
        return SCSI_DISK8_MAJOR + major_idx - 8;
    default:
        /* this shouldn't happen... but if it does, return -1 */
        return -1;
    }
}

struct devmajor {
    char *name;
    short major;
};

static struct devmajor dynamic_major_cache[] = {
    { "virtblk",     -1 },
    { "cciss8",      -1 },
    { "cciss9",      -1 },
    { "cciss10",     -1 },
    { "cciss11",     -1 },
    { "cciss12",     -1 },
    { "cciss13",     -1 },
    { "cciss14",     -1 },
    { "cciss15",     -1 },
    { "cciss16",     -1 },
    { "cciss17",     -1 },
    { "cciss18",     -1 },
    { "cciss19",     -1 },
    { "cciss20",     -1 },
    { "cciss21",     -1 },
    { "cciss22",     -1 },
    { "cciss23",     -1 },
    { "cciss24",     -1 },
    { "cciss25",     -1 },
    { "cciss26",     -1 },
    { "cciss27",     -1 },
    { "cciss28",     -1 },
    { "cciss29",     -1 },
    { "cciss30",     -1 },
    { "cciss31",     -1 },
};

int majCacheSize = sizeof(dynamic_major_cache) / sizeof(struct devmajor);

/* 
 * find dynamically assigned major in /proc/devices
 */
static int dynamic_major(char *devname) {
    FILE *f;
    int retval = -1;
    int cacheIdx;

    /* look into cache */
    for (cacheIdx = 0; cacheIdx < majCacheSize; cacheIdx++) {
        if (!strcmp(dynamic_major_cache[cacheIdx].name, devname)) {
	    retval = dynamic_major_cache[cacheIdx].major;
	    break;
        }
    }

    if (retval != -1)
        return retval;

    f = fopen("/proc/devices", "r");
    if (!f)
        return -1;

    while (1) {
        char line[1024], *p, *e = NULL;
        long major;

        if (!fgets(line, sizeof(line), f))
            break;

        p = line;
        while (*p == ' ')
            p++;

        major = strtol(p, &e, 10);
        if (e == p ||
            (errno == ERANGE && (major == LONG_MIN || major == LONG_MAX)))
            continue;

        p = e;
        while (*p == ' ')
            p++;

        if (strncmp(p, devname, strlen(devname)) != 0)
            continue;

        retval = major;
        if (cacheIdx != majCacheSize)
            dynamic_major_cache[cacheIdx].major = major;

        break;
    }

    fclose(f);

    return retval;
}

/* virtio supports vda to vdzzz15
*/
static int virtio_minor(char * devName) {
    int minor;
    int i = 2;

    minor = (devName[i++] - 'a');

    if (devName[i] && !isdigit(devName[i])) {
	minor = ((minor + 1) * 26) + (devName[i++] - 'a');
	if (devName[i] && !isdigit(devName[i]))
	    minor = ((minor + 1) * 26) + (devName[i++] - 'a');
    }

    minor <<= 4;

    if (devName[i] && isdigit(devName[i])) {
	long part;
	char *e = NULL;

	part = strtol(&devName[i], &e, 10);
	if (e != &devName[i] &&
	    (errno != ERANGE || (part != LONG_MIN && part != LONG_MAX)))
	    minor += part;
    }

    return minor;
}

static const char digits[] = "0123456789";

int devMakeInode(char * devName, char * path) {
    int i;
    long int major, minor;
    int type;
    char *ptr;
    char *dir;

    if (!strncmp(devName, "mapper/", 7)) {
        struct dm_task *task;
        struct dm_info *info = alloca(sizeof *info);

        devName += 7;
        if (!info || !*devName)
            return -3;

        memset(info, '\0', sizeof (*info));
        task = dm_task_create(DM_DEVICE_INFO);
        if (!task)
            return -3;
        
        dm_task_set_name(task, devName);
        i = dm_task_run(task);
        if (i < 0) {
            dm_task_destroy(task);
            return -3;
        }
        i = dm_task_get_info(task, info);
        dm_task_destroy(task);
        if (i < 0) {
            return -3;
        }

	type = S_IFBLK;
        major = info->major;
        minor = info->minor;
    } else if (devName[0] == 's' && devName[1] == 'd') {
        /* scsi devices sda - sdp: major 8, minor 0 - 255 */
        /* scsi devices sdq - sdaf: major 65, minor 0 - 255 */
        /* scsi devices sdqg - sdav: major 66, minor 0 - 255 */
        /* etc... */
	int drive = 0;
	char *num = NULL;
	type = S_IFBLK;

	if (devName[3] && isdigit(devName[3])) {
	    drive = devName[2] - 'a';
	    num = devName + 3;
	} else if (devName[3] && islower(devName[3])) {
	    drive = ((devName[2] - 'a' + 1) * 26) + devName[3] - 'a';
	    num = devName + 4;	    
	} else
	    drive = devName[2] - 'a';
        
        major = sd_major((drive & 0xf0) >> 4);
        if (major < 0)
            return major;
	minor = (drive * 16) % 256;
        minor += (drive & 0xfff00);
	if (num && num[0] && num[1])
	   minor += (num[0] - '0') * 10 + (num[1] - '0');
	else if (num && num[0])
	   minor += (num[0] - '0');
    } else if (!strncmp(devName, "st", 2) || !strncmp(devName, "nst", 3)) {
        char *e = NULL;
        size_t s;

        s = strcspn(devName, digits);
        errno = 0;
        minor = strtol(devName+s, &e, 10);
        /* Silently ignore tape drives 32 and above */
        if (minor > 31)
            return 0;
        if (e == devName + s || 
            (errno == ERANGE &&
             (minor == LONG_MIN || minor == LONG_MAX)))
            return -1;
        switch (e[0]) {
            case 'a':   /* "st0a" and "nst0a" */
                minor += 32;
            case 'm':   /* "st0m" and "nst0m" */
                minor += 32;
            case 'l':   /* "st0l" and "nst0l" */
                minor += 32;
            case '\0':  /* "st0" and "nst0" */
                break;
            default:
                return -1;
        }

        if (devName[0] == 'n')
            minor += 128;
        if (minor > 255)
            return -1;

        major = 9;
        type = S_IFCHR;
    } else if (devName[0] == 'm' && devName[1] == 'd') {
	type = S_IFBLK;
	major = 9;
	minor = atoi(devName + 2);
    } else if (devName[0] == 'x' && devName[1] == 'v' && devName[2] == 'd') {
        /* xen xvd devices */
        type = S_IFBLK;
        major = 202;
	minor = ( devName[3] - 'a' ) * 16;
        if (devName[4] && isdigit(devName[4])) {
            if (devName[5] && isdigit(devName[5])) {
                minor += (devName[4] - '0') * 10 + (devName[5] - '0');
            } else {
                minor += devName[4] - '0';
            }
	}
    } else if (devName[0] == 'v' && devName[1] == 'd') {
        type = S_IFBLK;
        major = dynamic_major("virtblk");
        if (major < 0)
            return major;
        minor = virtio_minor(devName);
    } else if (devName[0] == 'u' && devName[1] == 'b') {
        /* usb block (ub) devices */
        type = S_IFBLK;
        major = 180;
	minor = ( devName[2] - 'a' ) * 8;
        if (devName[3] && isdigit(devName[3])) {
            minor += devName[3] - '0';
	}
    } else if (devName[0] == 's' && devName[1] == 'g') {
	type = S_IFBLK;
	major = 21;
	minor = atoi(devName + 2);
    } else if (!strncmp(devName, "loop", 4)) {
	type = S_IFBLK;
	major = 7;
	minor = atoi(devName + 4);
    } else if (!strncmp(devName, "scd", 3)) {
	type = S_IFBLK;
	major = 11;
	minor = atoi(devName + 3);
    } else if (devName[0] == 'h' && devName[1] == 'd') {
        int drive = 0;
	type = S_IFBLK;

        drive = devName[2] - 'a';
        if (drive > 19)
            return -1;

        major = idemajors[drive/2];
        minor = (drive % 2) * 64;

	if (devName[3] && devName[4])
	   minor += (devName[3] - '0') * 10 + (devName[4] - '0');
	else if (devName[3])
	   minor += (devName[3] - '0');
    } else if (!strncmp(devName, "ram", 3)) {
	type = S_IFBLK;
	major = 1;
	minor = 1;
	if (devName[3])
	    minor += devName[3] - '1';
#if defined (__s390__) || defined (__s390x__)
    } else if (!strncmp(devName, "dasd", 4) && strlen(devName) > 4) {
	/* IBM Dasd Drives */
	type = S_IFBLK;
	major = 94;
	minor = ( devName[4] - 'a' ) * 4;
        if (devName[5] && isalpha(devName[5])) {
            minor += 26 * 4 + ( devName[5] - 'a' ) * 4;
            if (devName[6] && isdigit(devName[6]) )
                minor += devName[6] - '0';
	} else if (devName[5] && isdigit(devName[5])) {
            minor += devName[5] - '0';
	}
    } else if (!strncmp(devName, "mnd", 4)) {
	/* IBM MiniDisk Drives */
	type = S_IFBLK;
	major = 95;
	minor = devName[3] - 'a';
#endif
    } else if (!strncmp(devName, "rd/", 3)) {
	/* dac 960 "/rd/c0d0{p1}" */
	int c, d, p, e;
	c = d = p = 0;
	e = sscanf(devName + 3, "c%dd%dp%d", &c, &d, &p);
	type = S_IFBLK;
	major = 48 + c;     /* controller */
	minor = d * 8;      /* disk */
	minor += p; 	    /* partition */
    } else if (!strncmp(devName, "ida/", 4)) {
	/* Compaq Smart Array "ida/c0d0{p1} */
	int c, d, p, e;
	c = d = p = 0;
	e = sscanf(devName + 4, "c%dd%dp%d", &c, &d, &p);
	type = S_IFBLK;
	major = 72 + c;     /* controller */
	minor = d * 16;     /* disk */
	minor += p; 	    /* partition */
    } else if (!strncmp(devName, "cciss/", 6)) {
	/* Compaq Smart Array 5300 "cciss/c0d0{p1} */
	int c, d, p, e;
	c = d = p = 0;
	e = sscanf(devName + 6, "c%dd%dp%d", &c, &d, &p);
	type = S_IFBLK;
        if (c < 8) {
            /* reserved major numbers */
            major = 104 + c;    /* controller */
    	} else {
            /* dynamically assigned major numbers */		
            char cname[11];
            snprintf(cname, 10, "cciss%d", c);	
            major = dynamic_major(cname); 
            if (major < 0)
                return major;
    	}
	minor = d * 16;     /* disk */
	minor += p; 	    /* partition */
    } else if (!strncmp(devName, "ataraid/", 8)) {
	type = S_IFBLK;
	major = 114;    /* controller */
	minor = (devName[9] - '0') * 16;  /* disk */
	if (strlen(devName) > 10)          /* partition */
	    minor += atoi(devName + 11);
    } else if (!strncmp(devName, "sx8/", 4)) {
	/* Promise SX8 "sx8/0{p1} */
	int d, p, e;
	d = p = 0;
	e = sscanf(devName + 4, "%dp%d", &d, &p);
	type = S_IFBLK;
	major = 160 + (d/8);    /* controller */
	minor = (d % 8) * 32;     /* disk */
	minor += p; 	    /* partition */
    } else if (!strncmp(devName, "i2o/", 4)) {
        /* I2O Block Device "i2o/hda */
        type = S_IFBLK;
        major = 80;    /* controller */
	minor = (devName[6] - 'a')*16;
	if ((devName[7]) && isdigit(devName[7]))
	{
		minor = minor + atoi(devName + 7);
	}
    } else if (!strncmp(devName, "iseries/vcd", 11)) {
        /* IBM virtual cdrom (iseries) */
        type = S_IFBLK;
        major = 113;
        minor = devName[11] - 'a';
    } else if (!strncmp(devName, "iseries/vd", 10)) {
	int drive = 0;
	char * num = NULL;

        /* IBM virtual disk (iseries) */
        type = S_IFBLK;
        major = 112;

	if (devName[11] && isdigit(devName[11])) {
	  drive = devName[10] - 'a';
	  num = devName + 11;
	} else if (devName[11] && islower(devName[11])) {
	  drive = ((devName[10] - 'a' + 1) * 26) + devName[11] - 'a';
	  num = devName + 12;
	} else {
	  drive = devName[10] - 'a';
	}

	minor = (drive * 8);
	if (num && num[0])
	    minor += (num[0] - '0');
    } else {
	for (i = 0; i < numDevices; i++) {
	    if (!strcmp(devices[i].name, devName)) break;
	}
	if (i == numDevices) return -1;
	major = devices[i].major;
	minor = devices[i].minor;

	if (devices[i].isChar)
	    type = S_IFCHR;
	else
	    type = S_IFBLK;
    }

    ptr = path;
    i = 0;
    while (*ptr)
      if (*ptr++ == '/')
	i++;
    if (i > 2) {
      dir = alloca(strlen(path) + 1);
      strcpy(dir, path);
      ptr = dir + (strlen(path) - 1);
      while (*ptr != '/')
	*ptr-- = '\0';
      mkdir(dir, 0644);
    }
    
    unlink(path);
    if (mknod(path, type | 0600, makedev(major, minor)) < 0)
	return -2;

    return 0;
}

#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>
#include <string.h>

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
    { "lp0",		6,	0,	1 },
    { "lp1",		6,	1,	1 },
    { "lp2",		6,	2,	1 },
    { "mcd",		23,	0,	0 },
    { "mcdx",		20,	0,	0 },
    { "nst0",		9,	128,	1 },
    { "optcd",		17,	0,	0 },
    { "psaux",		10,	1,	1 },
    { "sbpcd",		25,	0,	0 },
    { "scd0",		11,	0,	0 },
    { "scd1",		11,	1,	0 },
    { "sjcd",		18,	0,	0 },
    { "ttyS0",		4,	64,	1 },
    { "ttyS1",		4,	65,	1 },
    { "ttyS2",		4,	66,	1 },
    { "ttyS3",		4,	67,	1 },
};

int numDevices = sizeof(devices) / sizeof(struct devnum);

int devMakeInode(char * devName, char * path) {
    int i;
    int major, minor;
    int type;
    char *ptr;
    char *dir;

    /* scsi devices sda - sdp: major 8, minor 0 - 255 */
    /* scsi devices sdq - sdaf: major 65, minor 0 - 255 */
    /* scsi devices sdqg - sdav: major 66, minor 0 - 255 */
    /* etc... */
    if (devName[0] == 's' && devName[1] == 'd') {
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
	/* only 128 SCSI drives, sorry */
	if (drive > 128)
	    return -1;
	else if (drive < 16)
	    major = 8;
	else
	    major = 64 + (drive) / 16;
	minor = (drive * 16) % 256;
	if (num && num[0] && num[1])
	   minor += (num[0] - '0') * 10 + (num[1] - '0');
	else if (num && num[0])
	   minor += (num[0] - '0');
	if (minor > 255)
	    return -1;
    } else if (devName[0] == 'm' && devName[1] == 'd') {
	type = S_IFBLK;
	major = 9;
	minor = atoi(devName + 2);
    } else if (!strncmp(devName, "loop", 4)) {
	type = S_IFBLK;
	major = 7;
	minor = atoi(devName + 4);
    } else if (devName[0] == 'h' && devName[1] == 'd') {
	type = S_IFBLK;
	if (devName[2] == 'a')
	    major = 3, minor = 0;
	else if (devName[2] == 'b')
	    major = 3, minor = 64;
	else if (devName[2] == 'c')
	    major = 22, minor = 0;
	else if (devName[2] == 'd')
	    major = 22, minor = 64;
	else if (devName[2] == 'e')
	    major = 33, minor = 0;
	else if (devName[2] == 'f')
	    major = 33, minor = 64;
	else if (devName[2] == 'g')
	    major = 34, minor = 0;
	else if (devName[2] == 'h')
	    major = 34, minor = 64;
	else
	    return -1;

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
    } else if (!strncmp(devName, "rd/", 3)) {
	/* dac 960 "/rd/c0d0{p1}" */
	type = S_IFBLK;
	major = 48 + devName[4] - '0';   /* controller */
	minor = (devName[6] - '0') * 8;  /* disk */
	if (strlen(devName) > 7)         /* partition */
	    minor += devName[8] - '0';
    } else if (!strncmp(devName, "ida/", 4)) {
	/* Compaq Smart Array "ida/c0d0{p1} */
	type = S_IFBLK;
	major = 72 + devName[5] - '0';    /* controller */
	minor = (devName[7] - '0') * 16;  /* disk */
	if (strlen(devName) > 8)          /* partition */
	    minor += atoi(devName + 9);
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
    if (mknod(path, type | 0600, makedev(major, minor))) {
	return -2;
    }

    return 0;
}

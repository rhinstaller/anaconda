#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

struct devnum {
    char * name;
    short major, minor;
    int isChar;
};

static struct devnum devices[] = {
    { "aztcd",		29,	0,	0 },
    { "bpcd",		41,	0,	0 },
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
    { "sbpcd",		25,	0,	0 },
    { "scd0",		11,	0,	0 },
    { "scd1",		11,	1,	0 },
    { "sjcd",		18,	0,	0 },
};

int numDevices = sizeof(devices) / sizeof(struct devnum);

int devMakeInode(char * devName, char * path) {
    int i;
    int major, minor;
    int type;
    char *ptr;
    char *dir;

    if (devName[0] == 's' && devName[1] == 'd') {
	type = S_IFBLK;
	major = 8;
	minor = (devName[2] - 'a') << 4;
	if (devName[3] && devName[4])
	   minor += 10 + (devName[4] - '0');
	else if (devName[3])
	   minor += (devName[3] - '0');
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
	   minor += 10 + (devName[4] - '0');
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
	major = 72;                    /* controller */
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

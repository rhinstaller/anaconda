#ifndef H_IMOUNT
#define H_IMOUNT

#define IMOUNT_ERR_ERRNO	1
#define IMOUNT_ERR_OTHER	2

#include <sys/mount.h>		/* for umount() */

#define IMOUNT_RDONLY  1
#define IMOUNT_BIND    2
#define IMOUNT_REMOUNT 4

int doPwMount(char * dev, char * where, char * fs, int options, void * data);
int mkdirChain(char * origChain);

#endif

#ifndef H_IMOUNT
#define H_IMOUNT

#define IMOUNT_ERR_ERRNO	1
#define IMOUNT_ERR_OTHER	2

#include <sys/mount.h>		/* for umount() */

int doPwMount(char * dev, char * where, char * fs, int rdonly, int istty,
		     char * acct, char * pw);

#endif

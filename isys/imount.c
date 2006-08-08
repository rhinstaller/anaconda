#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "imount.h"
#include "sundries.h"

#define _(foo) foo

static int mkdirIfNone(char * directory);

int doPwMount(char * dev, char * where, char * fs, int options, void *data) {
    char * buf = NULL;
    int isnfs = 0;
    char * mount_opt = NULL;
    long int flag;
    char * chptr __attribute__ ((unused));
    
    if (!strcmp(fs, "nfs")) isnfs = 1;

    /*logMessage(INFO, "mounting %s on %s as type %s", dev, where, fs);*/

    if (mkdirChain(where))
        return IMOUNT_ERR_ERRNO;

    flag = MS_MGC_VAL;
    if (options & IMOUNT_RDONLY)
        flag |= MS_RDONLY;
    if (options & IMOUNT_BIND)
        flag |= MS_BIND;
    if (options & IMOUNT_REMOUNT)
        flag |= MS_REMOUNT;

    if (!isnfs && (*dev == '/' || !strcmp(dev, "none"))) {
        buf = dev;
    } else if (!isnfs) {
        buf = alloca(200);
        strcpy(buf, "/tmp/");
        strcat(buf, dev);
    } else {
#ifndef DISABLE_NETWORK
        char * extra_opts = NULL;
        int flags = 0;

        if (data)
            extra_opts = strdup(data);

        buf = dev;
        /*logMessage(INFO, "calling nfsmount(%s, %s, &flags, &extra_opts, &mount_opt)",
			buf, where);*/

        if (nfsmount(buf, where, &flags, &extra_opts, &mount_opt, 0)) {
		/*logMessage(INFO, "\tnfsmount returned non-zero");*/
		/*fprintf(stderr, "nfs mount failed: %s\n",
			nfs_error());*/
		return IMOUNT_ERR_OTHER;
        }
#endif
	}
    if (!strncmp(fs, "vfat", 4))
        mount_opt="check=relaxed";
#ifdef __sparc__
    if (!strncmp(fs, "ufs", 3))
        mount_opt="ufstype=sun";
#endif

    /*logMessage(INFO, "calling mount(%s, %s, %s, %ld, %p)", buf, where, fs, 
      flag, mount_opt);*/
    
    if (mount(buf, where, fs, flag, mount_opt)) {
        /*logMessage(ERROR, "mount failed: %s", strerror(errno));*/
        return IMOUNT_ERR_ERRNO;
    }

    return 0;
}

int mkdirChain(char * origChain) {
    char * chain;
    char * chptr;

    chain = alloca(strlen(origChain) + 1);
    strcpy(chain, origChain);
    chptr = chain;

    while ((chptr = strchr(chptr, '/'))) {
	*chptr = '\0';
	if (mkdirIfNone(chain)) {
	    *chptr = '/';
	    return IMOUNT_ERR_ERRNO;
	}

	*chptr = '/';
	chptr++;
    }

    if (mkdirIfNone(chain))
	return IMOUNT_ERR_ERRNO;

    return 0;
}

static int mkdirIfNone(char * directory) {
    int rc, mkerr;
    char * chptr;

    /* If the file exists it *better* be a directory -- I'm not going to
       actually check or anything */
    if (!access(directory, X_OK)) return 0;

    /* if the path is '/' we get ENOFILE not found" from mkdir, rather
       then EEXIST which is weird */
    for (chptr = directory; *chptr; chptr++)
        if (*chptr != '/') break;
    if (!*chptr) return 0;

    rc = mkdir(directory, 0755);
    mkerr = errno;

    if (!rc || mkerr == EEXIST) return 0;

    return IMOUNT_ERR_ERRNO;
}

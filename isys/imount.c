#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/errno.h>
#include <sys/mount.h>
#include <unistd.h>

#include "imount.h"

#define _(foo) foo

static int mkdirChain(char * chain);
static int mkdirIfNone(char * directory);

int doPwMount(char * dev, char * where, char * fs, int rdonly, int istty,
		     char * acct, char * pw) { 
    char * buf = NULL;
    int isnfs = 0;
    char * mount_opt = NULL;
    long int flag;
    char * chptr;
    
    if (!strcmp(fs, "nfs")) isnfs = 1;

    /*logMessage("mounting %s on %s as type %s", dev, where, fs);*/

    if (!strcmp(fs, "smb")) {
#if 0 /* disabled for now */
	mkdirChain(where);

	if (!acct) acct = "guest";
	if (!pw) pw = "";

	buf = alloca(strlen(dev) + 1);
	strcpy(buf, dev);
	chptr = buf;
	while (*chptr && *chptr != ':') chptr++;
	if (!*chptr) {
	    /*logMessage("bad smb mount point %s", where);*/
	    return IMOUNT_ERR_OTHER;
	} 
	
	*chptr = '\0';
	chptr++;

#ifdef __i386__
	/*logMessage("mounting smb filesystem from %s path %s on %s",
			buf, chptr, where);*/
	return smbmount(buf, chptr, acct, pw, "localhost", where);
#else 
	errorWindow("smbfs only works on Intel machines");
#endif
#endif /* disabled */
    } else {
	if (mkdirChain(where))
	    return IMOUNT_ERR_ERRNO;

  	if (!isnfs && *dev == '/') {
	    buf = dev;
	} else if (!isnfs) {
	    buf = alloca(200);
	    strcpy(buf, "/tmp/");
	    strcat(buf, dev);
	} else {
#ifndef DISABLE_NETWORK
	    char * extra_opts = NULL;
	    int flags = 0;

	    buf = dev;
	    /*logMessage("calling nfsmount(%s, %s, &flags, &extra_opts, &mount_opt)",
			buf, where);*/

	    if (nfsmount(buf, where, &flags, &extra_opts, &mount_opt)) {
		/*logMessage("\tnfsmount returned non-zero");*/
		/*fprintf(stderr, "nfs mount failed: %s\n",
			nfs_error());*/
		return IMOUNT_ERR_OTHER;
	    }
#endif
	}
	flag = MS_MGC_VAL;
	if (rdonly)
	    flag |= MS_RDONLY;

	if (!strncmp(fs, "vfat", 4))
	    mount_opt="check=relaxed";
	#ifdef __sparc__
	if (!strncmp(fs, "ufs", 3))
	    mount_opt="ufstype=sun";
	#endif

	/*logMessage("calling mount(%s, %s, %s, %ld, %p)", buf, where, fs, 
			flag, mount_opt);*/

	if (mount(buf, where, fs, flag, mount_opt)) {
 	    return IMOUNT_ERR_ERRNO;
	}
    }

    return 0;
}

static int mkdirChain(char * origChain) {
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

#include <stdio.h>
#include <stdlib.h>
#include <sys/errno.h>
#include <sys/mount.h>

#include "imount.h"

#define _(foo) foo

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
	/*mkdirChain(where);*/

	if (!acct) acct = "guest";
	if (!pw) pw = "";

	buf = alloca(strlen(dev) + 1);
	strcpy(buf, dev);
	chptr = buf;
	while (*chptr && *chptr != ':') chptr++;
	if (!*chptr) {
	    /*logMessage("bad smb mount point %s", where);*/
	    return 0;
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
	/*mkdirChain(where);*/

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
		fprintf(stderr, "nfs mount failed: %s\n",
			nfs_error());
		return 1;
	    }
#endif
	}
	flag = MS_MGC_VAL;
	if (rdonly)
	    flag |= MS_RDONLY;

	if (!strncmp(fs, "vfat", 4))
	    mount_opt="check=relaxed";

	/*logMessage("calling mount(%s, %s, %s, %ld, %p)", buf, where, fs, 
			flag, mount_opt);*/

	if (mount(buf, where, fs, flag, mount_opt)) {
	    fprintf(stderr, "mount failed: %s\n", strerror(errno));
 	    return 1;
	}
    }

    return 0;
}


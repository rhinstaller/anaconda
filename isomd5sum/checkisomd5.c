/* simple program to check implanted md5sum in an iso 9660 image   */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "md5.h"
#include "libcheckisomd5.h"

int main(int argc, char **argv) {
    int i;
    int rc;
    int flags;
    int verbose;
    int gauge;
    int md5only;
    int filearg;

    if (argc < 2) {
	printf("Usage: checkisomd5 [--md5sumonly] [--verbose] [--gauge] <isofilename>|<blockdevice>\n\n");
	exit(1);
    }

    md5only = 0;
    flags = 1; /* mediaCheckFile defaults to verbose, not quiet, so prepopulate the "quiet" bit */
    verbose = 0;
    gauge = 1;
    filearg = 1;
    for (i=1; i < argc; i++) {
	if (strcmp(argv[i], "--md5sumonly") == 0) {
	    md5only = 1;
	    filearg++;
	} else if (strcmp(argv[i], "--verbose") == 0) {
	    filearg++;
	    flags ^= 1;
	    verbose = 1;
	} else if (strcmp(argv[i], "--gauge") == 0) {
	    filearg++;
	    flags ^= 2;
	    gauge = 1;
	} else 
	    break;
    }

    if (md5only|verbose)
	printMD5SUM(argv[filearg]);

    if (md5only)
	exit(0);

    rc = mediaCheckFile(argv[filearg], flags);

    /* 1 means it passed, 0 means it failed, -1 means we couldnt find chksum */
    if (rc == 1)
	exit(0);
    else
	exit(1);
}
 

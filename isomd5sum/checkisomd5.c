/* simple program to check implanted md5sum in an iso 9660 image   */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

#include <stdio.h>

#include "md5.h"
#include "libcheckisomd5.h"

int main(int argc, char **argv) {
    int rc;

    if (argc < 2) {
	printf("Usage: checkisomd5 [--md5sumonly] <isofilename>|<blockdevice>\n\n");
	exit(1);
    }

    /* see if they just want md5sum */
    if (strcmp(argv[1], "--md5sumonly") == 0) {
	printMD5SUM(argv[2]);
	exit(0);
    }

    rc = mediaCheckFile(argv[1]);

    exit(rc ? 0 : 1);
}

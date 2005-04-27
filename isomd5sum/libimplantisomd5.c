/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

/*   4/2005	Dustin Kirkland	(dustin.kirkland@gmail.com)        */
/* 	Added support for checkpoint fragment sums;                */
/*	Allows for exiting media check when bad fragment md5sum'ed */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

#include "md5.h"
#include "libimplantisomd5.h"

#define APPDATA_OFFSET 883
#define SIZE_OFFSET 84

/* Length in characters of string used for fragment md5sum checking  */
#define FRAGMENT_SUM_LENGTH 60
/* FRAGMENT_COUNT must be an integral divisor or FRAGMENT_SUM_LENGTH */
/* 60 => 2, 3, 4, 5, 6, 10, 12, 15, 20, or 30 */
#define FRAGMENT_COUNT 20

/* number of sectors to ignore at end of iso when computing sum */
#define SKIPSECTORS 15

#define MAX(x, y)  ((x > y) ? x : y)
#define MIN(x, y)  ((x < y) ? x : y)

/* finds primary volume descriptor and returns info from it */
/* mediasum must be a preallocated buffer at least 33 bytes long */
static int parsepvd(int isofd, char *mediasum, long long *isosize) {
    unsigned char buf[2048];
    long long offset;
    unsigned char *p __attribute__((unused));

    if (lseek(isofd, 16*2048, SEEK_SET) == -1)
	return ((long long)-1);
    
    offset = (16 * 2048);
    for (;1;) {
        if (read(isofd, buf, 2048L) == -1)
	    return ((long long)-1);

	if (buf[0] == 1)
	    /* found primary volume descriptor */
	    break;
	else if (buf[0] == 255)
	    /* hit end and didn't find primary volume descriptor */
	    return ((long long)-1);
	offset += 2048L;
    }
    
    /* read out md5sum */
#if 0
    memcpy(mediasum, buf + APPDATA_OFFSET + 13, 32);
    mediasum[32] = '\0';

    for (p=mediasum; *p; p++)
	if (*p != ' ')
	    break;

    /* if the md5sum was all spaces, we didn't find md5sum */
    if (!*p)
	return -1;
#endif

    /* get isosize */
    *isosize = (buf[SIZE_OFFSET]*0x1000000+buf[SIZE_OFFSET+1]*0x10000 +
		buf[SIZE_OFFSET+2]*0x100 + buf[SIZE_OFFSET+3]) * 2048LL;

    return offset;
}


static unsigned int writeAppData(unsigned char *appdata, char *valstr, unsigned int loc) {
    if (loc + strlen(valstr) > 511) {
	printf("Attempted to write too much appdata, exiting...\n");
	exit(-1);
    }

    memcpy(appdata + loc, valstr, strlen(valstr));

    return loc+strlen(valstr);
}




int implantISOFile(char *fname, int supported, int forceit, int quiet, char **errstr) {
    int i;
    int isofd;
    int nread;
    int dirty;
    int pvd_offset;
    int current_fragment = 0;
    int previous_fragment = 0;
    int nattempt;
    long long isosize, total;
    unsigned char md5sum[16];
    unsigned char fragmd5sum[16];
    unsigned int loc;
    unsigned int bufsize = 32768;
    unsigned char *buf;
    unsigned char orig_appdata[512];
    unsigned char new_appdata[512];
    char mediasum[33];
    char md5str[40];
    char fragstr[FRAGMENT_SUM_LENGTH+1];
    MD5_CTX md5ctx, fragmd5ctx;

    isofd = open(fname, O_RDWR);

    if (isofd < 0) {
	*errstr = "Error - Unable to open file %s\n\n";
	return -1;
    }

    pvd_offset = parsepvd(isofd, mediasum, &isosize);
    if (pvd_offset < 0) {
	*errstr = "Could not find primary volumne!\n\n";
	return -1;
    }

    lseek(isofd, pvd_offset + APPDATA_OFFSET, SEEK_SET);
    nread = read(isofd, orig_appdata, 512);

    if (!forceit) {
	dirty = 0;
	for (i=0; i < 512; i++)
	    if (orig_appdata[i] != ' ')
		dirty = 1;

	if (dirty) {
	    *errstr = "Application data has been used - not implanting md5sum!\n";
	    return -1;
	}
    } else {
	/* write out blanks to erase old app data */
	lseek(isofd, pvd_offset + APPDATA_OFFSET, SEEK_SET);
	memset(new_appdata, ' ', 512);
	i = write(isofd, new_appdata, 512);
	if (i<0) {
	    printf("write failed %d\n", i);
	    perror("");
	}
    }

    /* now do md5sum */
    lseek(isofd, 0L, SEEK_SET);

    MD5_Init(&md5ctx);
    *fragstr = '\0';
    buf = malloc(bufsize * sizeof(unsigned char));

    total = 0;
    /* read up to 15 sectors from end, due to problems reading last few */
    /* sectors on burned CDs                                            */
    while (total < isosize - SKIPSECTORS*2048) {
        nattempt = MIN(isosize - SKIPSECTORS*2048 - total, bufsize);
	nread = read(isofd, buf, nattempt);

	if (nread <= 0)
	    break;
	
	MD5_Update(&md5ctx, buf, nread);

        /* if we're onto the next fragment, calculate the previous sum and write */
        current_fragment = total * (FRAGMENT_COUNT+1) / (isosize - SKIPSECTORS*2048);
        if ( current_fragment != previous_fragment ) {
	    memcpy(&fragmd5ctx, &md5ctx, sizeof(MD5_CTX));
            MD5_Final(fragmd5sum, &fragmd5ctx);
            for (i=0; i<FRAGMENT_SUM_LENGTH/FRAGMENT_COUNT; i++) {
                char tmpstr[2];
                snprintf(tmpstr, 2, "%01x", fragmd5sum[i]);
                strncat(fragstr, tmpstr, 2);
            }
            /*  printf("\nFragment [%i]: %s\n", previous_fragment, fragstr);  */
            previous_fragment = current_fragment;
        }

	total = total + nread;
    }
    free(buf);

    MD5_Final(md5sum, &md5ctx);

    *md5str = '\0';
    for (i=0; i<16; i++) {
	char tmpstr[4];
	snprintf (tmpstr, 4, "%02x", md5sum[i]);
	strncat(md5str, tmpstr, 2);
    }

    if (!quiet) {
	printf("Inserting md5sum into iso image...\n");
	printf("md5 = %s\n", md5str);
	printf("Inserting fragment md5sums into iso image...\n");
	printf("fragmd5 = %s\n", fragstr);
	printf("frags = %d\n", FRAGMENT_COUNT);
    }
    /*    memcpy(new_appdata, orig_appdata, 512); */
    memset(new_appdata, ' ', 512);

    loc = 0;
    loc = writeAppData(new_appdata, "ISO MD5SUM = ", loc);
    loc = writeAppData(new_appdata, md5str, loc);
    loc = writeAppData(new_appdata, ";", loc);

    buf = malloc(512 * sizeof(unsigned char));
    snprintf((char *)buf, 512, "SKIPSECTORS = %d", SKIPSECTORS);

    loc = writeAppData(new_appdata, (char *)buf, loc);
    loc = writeAppData(new_appdata, ";", loc);
    free(buf);

    if (supported) {
	if (!quiet)
	    printf("Setting supported flag to 1\n");
	loc = writeAppData(new_appdata, "RHLISOSTATUS=1", loc);
    } else {
	if (!quiet)
	    printf("Setting supported flag to 0\n");
	loc = writeAppData(new_appdata, "RHLISOSTATUS=0", loc);
    }
	
    loc = writeAppData(new_appdata, ";", loc);

    loc = writeAppData(new_appdata, "FRAGMENT SUMS = ", loc);
    loc = writeAppData(new_appdata, fragstr, loc);
    loc = writeAppData(new_appdata, ";", loc);

    buf = malloc(512 * sizeof(unsigned char));
    snprintf((char *)buf, 512, "FRAGMENT COUNT = %d", FRAGMENT_COUNT);
    loc = writeAppData(new_appdata, (char *)buf, loc);
    loc = writeAppData(new_appdata, ";", loc);
    free(buf);

    loc = writeAppData(new_appdata, "THIS IS NOT THE SAME AS RUNNING MD5SUM ON THIS ISO!!", loc);
    
    i = lseek(isofd, pvd_offset + APPDATA_OFFSET, SEEK_SET);
    if (i<0)
	printf("seek failed\n");

    i = write(isofd, new_appdata, 512);
    if (i<0) {
	printf("write failed %d\n", i);
	perror("");
    }

    close(isofd);
    errstr = NULL;
    return 0;
}

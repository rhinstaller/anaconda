/* simple program to insert a md5sum into application data area of */
/* an iso9660 image                                                */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

#include "md5.h"

#define APPDATA_OFFSET 883
#define SIZE_OFFSET 84

/* number of sectors to ignore at end of iso when computing sum */
#define SKIPSECTORS 15

#define MAX(x, y)  ((x > y) ? x : y)
#define MIN(x, y)  ((x < y) ? x : y)

/* finds primary volume descriptor and returns info from it */
/* mediasum must be a preallocated buffer at least 33 bytes long */
int parsepvd(int isofd, char *mediasum, long long *isosize) {
    unsigned char buf[2048];
    long long offset;
    unsigned char *p;

    if (lseek(isofd, (off_t)(16L * 2048L), SEEK_SET) == -1)
	return ((long long)-1);

    offset = (16L * 2048L);
    for (;1;) {
	read(isofd, buf, 2048);
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



int main(int argc, char **argv) {
    int isofd;
    int nread;
    int i;
    int dirty;
    int pvd_offset;
    int forceit;
    long long isosize;
    unsigned char md5sum[16];
    unsigned int total;
    unsigned char *fname;
    unsigned char buf[2048];
    unsigned char orig_appdata[512];
    unsigned char new_appdata[512];
    unsigned char mediasum[33], computedsum[33];
    char md5str[40];
    MD5_CTX md5ctx;

    if (argc < 2) {
	printf("Usage: implantisomd5 [-f] <isofilename>\n\n");
	exit(1);
    }

    if (!strncmp(argv[1] , "-f", 3)) {
	forceit = 1;
	fname = argv[2];
    } else {
	forceit = 0;
	fname = argv[1];
    }

    isofd = open(fname, O_RDWR);

    if (isofd < 0) {
	fprintf(stderr, "Error - Unable to open file %s\n\n", fname);
	exit(1);
    }

    pvd_offset = parsepvd(isofd, mediasum, &isosize);
    if (pvd_offset < 0) {
	fprintf(stderr, "Could not find primary volumne!\n\n");
	exit(1);
    }

    lseek(isofd, pvd_offset + APPDATA_OFFSET, SEEK_SET);
    nread = read(isofd, orig_appdata, 512);

    if (!forceit) {
	dirty = 0;
	for (i=0; i < 512; i++)
	    if (orig_appdata[i] != ' ')
		dirty = 1;

	if (dirty) {
	    fprintf(stderr, "Application data has been used - not implanting md5sum!\n");
	    exit(1);
	}
    }


    lseek(isofd, 0L, SEEK_SET);

    MD5_Init(&md5ctx);

    total = 0;
    /* read up to 15 sectors from end, due to problems reading last few */
    /* sectors on burned CDs                                            */
    while (total < isosize - SKIPSECTORS*2048) {
	nread = read(isofd, buf, 2048);
	if (nread <= 0)
	    break;

	MD5_Update(&md5ctx, buf, nread);
	total = total + nread;
    }

    MD5_Final(md5sum, &md5ctx);

    *md5str = '\0';
    for (i=0; i<16; i++) {
	char tmpstr[4];
	snprintf (tmpstr, 4, "%02x", md5sum[i]);
	strcat(md5str, tmpstr);
    }

    printf("Inserting md5sum into iso image...\n");
    printf("md5 = %s\n", md5str);
    /*    memcpy(new_appdata, orig_appdata, 512); */
    memset(new_appdata, ' ', 512);
    memcpy(new_appdata, "ISO MD5SUM = ", 13);
    memcpy(new_appdata+13, md5str, 33);
    memcpy(new_appdata+47, "THIS IS NOT THE SAME AS RUNNING MD5SUM ON THIS ISO!!", 51);

    i = lseek(isofd, pvd_offset + APPDATA_OFFSET, SEEK_SET);
    if (i<0)
	printf("seek failed\n");

    i = write(isofd, new_appdata, 512);
    if (i<0) {
	printf("write failed %d\n", i);
	perror("");
    }

    close(isofd);

    printf("Done!\n");
}

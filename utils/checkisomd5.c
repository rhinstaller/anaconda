/* simple program to check implanted md5sum in an iso 9660 image   */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

#include "md5.h"


/* number of sectors to ignore at end of iso when computing sum */
#define SKIPSECTORS 150

#define APPDATA_OFFSET 883
#define SIZE_OFFSET 84

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
    memcpy(mediasum, buf + APPDATA_OFFSET + 13, 32);
    mediasum[32] = '\0';

    for (p=mediasum; *p; p++)
	if (*p != ' ')
	    break;

    /* if the md5sum was all spaces, we didn't find md5sum */
    if (!*p)
	return -1;

    /* get isosize */
    *isosize = (buf[SIZE_OFFSET]*0x1000000+buf[SIZE_OFFSET+1]*0x10000 +
		buf[SIZE_OFFSET+2]*0x100 + buf[SIZE_OFFSET+3]) * 2048LL;

    return offset;
}

/* returns -1 if no checksum encoded in media, 0 if no match, 1 if match */
/* mediasum is the sum encoded in media, computedsum is one we compute   */
/* both strings must be pre-allocated at least 33 chars in length        */
int checkmd5sum(int isofd, char *mediasum, char *computedsum) {
    int nread;
    int i;
    int appdata_start_offset, appdata_end_offset;
    int nattempt;
    unsigned int bufsize = 32768;
    unsigned char md5sum[16];
    unsigned int len;
    unsigned char *buf;
    unsigned long tally_inc, tally;
    long long isosize, offset, pvd_offset, apoff;
    MD5_CTX md5ctx;

    if ((pvd_offset = parsepvd(isofd, mediasum, &isosize)) < 0)
	return -1;

    /*    printf("Mediasum = %s\n",mediasum); */

    /* rewind, compute md5sum */
    lseek(isofd, 0L, SEEK_SET);

    MD5_Init(&md5ctx);

    offset = 0;
    apoff = pvd_offset + APPDATA_OFFSET;

    buf = malloc(bufsize * sizeof(unsigned char));
    tally_inc = 50*1000*1000;
    tally = 0;
    while (offset < isosize - SKIPSECTORS*2048) {
	nattempt = MIN(isosize - SKIPSECTORS*2048 - offset, bufsize);

	/*	printf("%lld %lld %lld %d\n", offset, isosize, isosize-SKIPSECTORS*2048, nattempt); */

	nread = read(isofd, buf, nattempt);
	if (nread <= 0)
	    break;

	/* overwrite md5sum we implanted with original data */
	if (offset < apoff && offset+nread >= apoff) {
	    appdata_start_offset = apoff - offset;
	    appdata_end_offset = MIN(appdata_start_offset+MIN(nread, 512),
				     offset + nread - apoff);
	    len = appdata_end_offset - appdata_start_offset;
	    memset(buf+appdata_start_offset, ' ', len);
	} else if (offset >= apoff && offset+nread < apoff + 512) {
	    appdata_start_offset = 0;
	    appdata_end_offset = nread;
	    len = appdata_end_offset - appdata_start_offset;
	    memset(buf+appdata_start_offset, ' ', len);
	} else if (offset < apoff + 512 && offset+nread >= apoff + 512) {
	    appdata_start_offset = 0;
	    appdata_end_offset = apoff + 512 - offset;
	    len = appdata_end_offset - appdata_start_offset;
	    memset(buf+appdata_start_offset, ' ', len);
	}

	MD5_Update(&md5ctx, buf, nread);
	offset = offset + nread;
	if (offset >= tally) {
	    printf("Read %5d MB\n", tally/1000/1000);
	    tally += tally_inc;
	}
    }

    sleep(1);

    free(buf);

    MD5_Final(md5sum, &md5ctx);

    *computedsum = '\0';
    for (i=0; i<16; i++) {
	char tmpstr[4];
	snprintf (tmpstr, 4, "%02x", md5sum[i]);
	strcat(computedsum, tmpstr);
    }

    /*    printf("mediasum, computedsum = %s %s\n", mediasum, computedsum); */

    if (strcmp(mediasum, computedsum))
	return 0;
    else
	return 1;
    }


int main(int argc, char **argv) {
    int isofd;
    int rc;
    int retval;
    unsigned char mediasum[33], computedsum[33];

    if (argc < 2) {
	printf("Usage: checkisomd5 <isofilename>\n\n");
	exit(1);
    }

    isofd = open(argv[1], O_RDONLY);

    if (isofd < 0) {
	fprintf(stderr, "Error - Unable to open file %s\n\n", argv[1]);
	exit(1);
    }
    
    rc = checkmd5sum(isofd, mediasum, computedsum);
    printf("%s\n%s\n", mediasum, computedsum);
    if ( rc == 0)
	printf("Md5sums differ.\n");
    else if (rc > 0)
	printf("Md5sums match.\n");
    else
	printf("No checksum information in iso, check skipped.\n");

    close(isofd);
    exit(0);
}


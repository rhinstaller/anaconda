/* simple program to insert a md5sum into application data area of */
/* an iso9660 image                                                */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <popt.h>

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
	if (read(isofd, buf, 2048) < 0)
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


unsigned int writeAppData(unsigned char *appdata, char *valstr, unsigned int loc) {
    if (loc + strlen(valstr) > 511) {
	printf("Attempted to write too much appdata, exiting...\n");
	exit(-1);
    }

    memcpy(appdata + loc, valstr, strlen(valstr));

    return loc+strlen(valstr);
}


static void usage(void) {
    fprintf(stderr, "implantisomd5:         implantisomd5 [--force] [--supported] <isofilename>\n");
    exit(1);
}


int main(int argc, char **argv) {
    int i;
    int rc;
    int isofd;
    int nread;
    int dirty;
    int pvd_offset;
    int forceit=0;
    int supported=0;
    int help=0;
    long long isosize;
    const char **args;
    unsigned char md5sum[16];
    unsigned int total;
    unsigned int loc;
    unsigned char *fname;
    unsigned char buf[2048];
    unsigned char orig_appdata[512];
    unsigned char new_appdata[512];
    unsigned char mediasum[33], computedsum[33];
    char md5str[40];
    MD5_CTX md5ctx;

    poptContext optCon;
    struct poptOption options[] = {
	{ "force", 'f', POPT_ARG_NONE, &forceit, 0 },
	{ "supported-iso", 'S', POPT_ARG_NONE, &supported, 0 },
	{ "help", 'h', POPT_ARG_NONE, &help, 0},
	{ 0, 0, 0, 0, 0}
    };


    optCon = poptGetContext("implantisomd5", argc, (const char **)argv, options, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
        fprintf(stderr, "bad option %s: %s\n",
		poptBadOption(optCon, POPT_BADOPTION_NOALIAS),
		poptStrerror(rc));
        exit(1);
    }

    if (help)
	usage();

    args = poptGetArgs(optCon);
    if (!args || !args[0] || !args[0][0])
        usage();

    fname = args[0];

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

    loc = 0;
    loc = writeAppData(new_appdata, "ISO MD5SUM = ", loc);
    loc = writeAppData(new_appdata, md5str, loc);
    loc = writeAppData(new_appdata, ";", loc);
    snprintf(buf, sizeof(buf), "SKIPSECTORS = %d", SKIPSECTORS);
    loc = writeAppData(new_appdata, buf, loc);
    loc = writeAppData(new_appdata, ";", loc);

    if (supported) {
	printf("Setting supported flag to 1\n");
	loc = writeAppData(new_appdata, "RHLISOSTATUS=1", loc);
    } else {
	printf("Setting supported flag to 0\n");
	loc = writeAppData(new_appdata, "RHLISOSTATUS=0", loc);
    }
	
    loc = writeAppData(new_appdata, ";", loc);

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

    printf("Done!\n");
    exit(0);
}

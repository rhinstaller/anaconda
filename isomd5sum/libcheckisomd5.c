/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

/*   4/2005	Dustin Kirkland	(dustin.kirkland@gmail.com)        */
/* 	Added support for checkpoint fragment sums;                */
/*	Exits media check as soon as bad fragment md5sum'ed        */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#include "md5.h"
#include "libcheckisomd5.h"

#define APPDATA_OFFSET 883
#define SIZE_OFFSET 84

/* Length in characters of string used for fragment md5sum checking */
#define FRAGMENT_SUM_LENGTH 60

#define MAX(x, y)  ((x > y) ? x : y)
#define MIN(x, y)  ((x < y) ? x : y)

/* finds primary volume descriptor and returns info from it */
/* mediasum must be a preallocated buffer at least 33 bytes long */
/* fragmentsums must be a preallocated buffer at least FRAGMENT_SUM_LENGTH+1 bytes long */
static int parsepvd(int isofd, char *mediasum, int *skipsectors, long long *isosize, int *supported, char *fragmentsums, long long *fragmentcount) {
    unsigned char buf[2048];
    char buf2[512];
    char tmpbuf[512];
    int skipfnd, md5fnd, supportedfnd, fragsumfnd, fragcntfnd;
    unsigned int loc;
    long long offset;
    char *p;

    if (lseek(isofd, (off_t)(16L * 2048L), SEEK_SET) == -1)
	return ((long long)-1);

    offset = (16L * 2048L);
    for (;1;) {
	if (read(isofd, buf, 2048) <= 0)
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
    memcpy(buf2, buf + APPDATA_OFFSET, 512);
    buf2[511] = '\0';

    *supported = 0;

    md5fnd = 0;
    skipfnd = 0;
    fragsumfnd = 0;
    fragcntfnd = 0;
    supportedfnd = 0;
    loc = 0;
    while (loc < 512) {
	if (!strncmp(buf2 + loc, "ISO MD5SUM = ", 13)) {

	    /* make sure we dont walk off end */
	    if ((loc + 32 + 13) > 511)
		return -1;

	    memcpy(mediasum, buf2 + loc + 13, 32);
	    mediasum[32] = '\0';
	    md5fnd = 1;
	    loc += 45;
	    for (p=buf2+loc; *p != ';' && loc < 512; p++, loc++);
	} else if (!strncmp(buf2 + loc, "SKIPSECTORS = ", 14)) {
	    char *errptr;

	    /* make sure we dont walk off end */
	    if ((loc + 14) > 511)
		return -1;

	    loc = loc + 14;
	    for (p=tmpbuf; buf2[loc] != ';' && loc < 512; p++, loc++)
		*p = buf2[loc];

	    *p = '\0';

	    *skipsectors = strtol(tmpbuf, &errptr, 10);
	    if (errptr && *errptr) {
 	        return -1;
	    } else {
 	        skipfnd = 1;
	    }

	    for (p=buf2+loc; *p != ';' && loc < 512; p++, loc++);
	} else if (!strncmp(buf2 + loc, "RHLISOSTATUS=1", 14)) {
	    *supported = 1;
	    supportedfnd = 1;
	    for (p=buf2+loc; *p != ';' && loc < 512; p++, loc++);
	} else if (!strncmp(buf2 + loc, "RHLISOSTATUS=0", 14)) {
	    *supported = 0;
	    supportedfnd = 1;
	    for (p=buf2+loc; *p != ';' && loc < 512; p++, loc++);
	} else if (!strncmp(buf2 + loc, "FRAGMENT SUMS = ", 16)) {
            /* make sure we dont walk off end */
            if ((loc + FRAGMENT_SUM_LENGTH) > 511)
                return -1;

            memcpy(fragmentsums, buf2 + loc + 16, FRAGMENT_SUM_LENGTH);
            fragmentsums[FRAGMENT_SUM_LENGTH] = '\0';
            fragsumfnd = 1;
            loc += FRAGMENT_SUM_LENGTH + 16;
            for (p=buf2+loc; *p != ';' && loc < 512; p++, loc++);
        } else if (!strncmp(buf2 + loc, "FRAGMENT COUNT = ", 17)) {
            char *errptr;
            /* make sure we dont walk off end */
            if ((loc + 17) > 511)
                return -1;

            loc = loc + 17;
            for (p=tmpbuf; buf2[loc] != ';' && loc < 512; p++, loc++)
                *p = buf2[loc];

            *p = '\0';

            *fragmentcount = strtol(tmpbuf, &errptr, 10);
            if (errptr && *errptr) {
                return -1;
            } else {
                fragcntfnd = 1;
            }

            for (p=buf2+loc; *p != ';' && loc < 512; p++, loc++);
        } else {
	    loc++;
	}

	if ((skipfnd & md5fnd & fragsumfnd & fragcntfnd) & supportedfnd)
 	    break;
    }

    if (!(skipfnd & md5fnd))
	return -1;

    /* get isosize */
    *isosize = (buf[SIZE_OFFSET]*0x1000000+buf[SIZE_OFFSET+1]*0x10000 +
		buf[SIZE_OFFSET+2]*0x100 + buf[SIZE_OFFSET+3]) * 2048LL;

    return offset;
}

/* returns -1 if no checksum encoded in media, 0 if no match, 1 if match */
/* mediasum is the sum encoded in media, computedsum is one we compute   */
/* both strings must be pre-allocated at least 33 chars in length        */
static int checkmd5sum(int isofd, char *mediasum, char *computedsum, int quiet) {
    int nread;
    int i, j;
    int appdata_start_offset, appdata_end_offset;
    int nattempt;
    int skipsectors;
    int supported;
    int current_fragment = 0;
    int previous_fragment = 0;
    int printed_frag_status = 0;
    unsigned int bufsize = 32768;
    unsigned char md5sum[16];
    unsigned char fragmd5sum[16];
    unsigned int len;
    unsigned char *buf;
    long long isosize, offset, pvd_offset, apoff;
    char fragmentsums[FRAGMENT_SUM_LENGTH];
    char thisfragsum[FRAGMENT_SUM_LENGTH];
    long long fragmentcount = 0;
    MD5_CTX md5ctx, fragmd5ctx;

    if ((pvd_offset = parsepvd(isofd, mediasum, &skipsectors, &isosize, &supported, fragmentsums, &fragmentcount)) < 0)
	return -1;

    /*    printf("Mediasum = %s\n",mediasum); */

    /* rewind, compute md5sum */
    lseek(isofd, 0L, SEEK_SET);

    MD5_Init(&md5ctx);

    offset = 0;
    apoff = pvd_offset + APPDATA_OFFSET;

    buf = malloc(bufsize * sizeof(unsigned char));
    if (!quiet) {
	printf("Percent complete: %05.1f%%", (100.0*offset)/(isosize-skipsectors*2048.0));
	fflush(stdout);
    }

    while (offset < isosize - skipsectors*2048) {
	nattempt = MIN(isosize - skipsectors*2048 - offset, bufsize);

	/*	printf("%lld %lld %lld %d\n", offset, isosize, isosize-SKIPSECTORS*2048, nattempt); */

	nread = read(isofd, buf, nattempt);
	if (nread <= 0)
	    break;

        if (nread > nattempt) {
            fprintf(stderr, "Warning: read got more data than requested\n");
            nread = nattempt;
            lseek(isofd, offset+nread, SEEK_SET);
        }
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
        if (fragmentcount) {
            current_fragment = offset * (fragmentcount+1) / (isosize - skipsectors*2048);
            /* if we're onto the next fragment, calculate the previous sum and check */
            if ( current_fragment != previous_fragment ) {
		memcpy(&fragmd5ctx, &md5ctx, sizeof(MD5_CTX));
                MD5_Final(fragmd5sum, &fragmd5ctx);
                *computedsum = '\0';
                j = (current_fragment-1)*FRAGMENT_SUM_LENGTH/fragmentcount;
                for (i=0; i<FRAGMENT_SUM_LENGTH/fragmentcount; i++) {
                    char tmpstr[2];
                    snprintf(tmpstr, 2, "%01x", fragmd5sum[i]);
                    strncat(computedsum, tmpstr, 2);
                    thisfragsum[i] = fragmentsums[j++];
                }
                thisfragsum[j] = '\0';
                if (!quiet) {
                    printf("   Fragment[%02i/%02lld] -> OK", previous_fragment+1, fragmentcount);
                    printed_frag_status = 1;
                    fflush(stdout);
                }
                previous_fragment = current_fragment;
                /* Exit immediately if current fragment sum is incorrect */
                if (strcmp(thisfragsum, computedsum) != 0) {
                    if (!quiet) {
                        printf("\nFragment %02i of %02lld is BAD!\n", previous_fragment+1, fragmentcount);
                    }
                    free(buf);
                    return 0;
                }
            }
        }
	offset = offset + nread;
	
	if (!quiet) {
            if (printed_frag_status) {
                printf("\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b");
                printed_frag_status = 0;
            }
	    printf("\b\b\b\b\b\b%05.1f%%", (100.0*offset)/(isosize-skipsectors*2048.0));
	    fflush(stdout);
	}
    }

    if (!quiet) {
	printf("\b\b\b\b\b\b\n%05.1f\n", (100.0*offset)/(isosize-skipsectors*2048.0));
    }

    sleep(1);

    free(buf);

    MD5_Final(md5sum, &md5ctx);

    *computedsum = '\0';
    for (i=0; i<16; i++) {
	char tmpstr[4];
	snprintf (tmpstr, 4, "%02x", md5sum[i]);
	strncat(computedsum, tmpstr, 2);
    }

    /*    printf("mediasum, computedsum = %s %s\n", mediasum, computedsum); */

    if (strcmp(mediasum, computedsum))
	return 0;
    else
	return 1;
}


#if 0
static void readCB(void *co, long long pos) {
    struct progressCBdata *data = co;
    static int tick = 0;
    char tickmark[2] = "-";
    char * ticks = "-\\|/";

    newtScaleSet(data->scale, pos);
    tick++;
    if (tick > 399) tick = 0;
    *tickmark = ticks[tick / 100];

    newtLabelSetText(data->label, tickmark);
    newtRefresh();
}
#endif

static int doMediaCheck(int isofd, char *mediasum, char *computedsum, long long *isosize, int *supported, int quiet) {
    int rc;
    int skipsectors;
    long long fragmentcount = 0;
    char fragmentsums[FRAGMENT_SUM_LENGTH+1];

    if (parsepvd(isofd, mediasum, &skipsectors, isosize, supported, fragmentsums, &fragmentcount) < 0) {
	fprintf(stderr, "Unable to read the disc checksum from the "
			 "primary volume descriptor.\nThis probably "
			 "means the disc was created without adding the "
			 "checksum.");
	return -1;
    }

    rc = checkmd5sum(isofd, mediasum, computedsum, quiet);

    return rc;
}

int mediaCheckFile(char *file, int quiet) {
    int isofd;
    int rc;
    char *result;
    char mediasum[33], computedsum[33];
    long long isosize;
    int supported;

    isofd = open(file, O_RDONLY);

    if (isofd < 0) {
	fprintf(stderr, "Unable to find install image %s\n", file);
	return -1;
    }

    rc = doMediaCheck(isofd, mediasum, computedsum, &isosize, &supported, quiet);

    close(isofd);

    /*    printf("isosize = %lld\n", isosize); 
	  printf("%s\n%s\n", mediasum, computedsum);*/

    if (!quiet)
	fprintf(stderr, "The supported flag value is %d\n", supported);

    if (rc == 0)
	result = "FAIL.\n\nIt is not recommended to use this media.";
    else if (rc > 0)
	result = "PASS.\n\nIt is OK to install from this media.";
    else
	result = "NA.\n\nNo checksum information available, unable to verify media.";

    if (!quiet)
	fprintf(stderr, "The media check is complete, the "
		"result is: %s\n", result);

    return rc;
}

void printMD5SUM(char *file) {
    int isofd;
    char mediasum[64];
    long long isosize;
    char fragmentsums[FRAGMENT_SUM_LENGTH+1];
    long long fragmentcount = 0;
    int supported;
    int skipsectors;

    isofd = open(file, O_RDONLY);

    if (isofd < 0) {
	fprintf(stderr, "%s: Unable to find install image.\n", file);
	exit(1);
    }

    if (parsepvd(isofd, mediasum, &skipsectors, &isosize, &supported, fragmentsums, &fragmentcount) < 0) {
	fprintf(stderr, "%s: Could not get pvd data", file);
	fprintf(stderr, "\nUnable to read the disc checksum from the "
			 "primary volume descriptor.\nThis probably "
			 "means the disc was created without adding the "
			 "checksum.");
	exit(1);
    }

    close(isofd);
    
    printf("%s:   %s\n", file, mediasum);
    if ( (strlen(fragmentsums) > 0) && (fragmentcount > 0) ) {
        printf("Fragment sums: %s\n", fragmentsums);
        printf("Fragment count: %lld\n", fragmentcount); 
    }
}

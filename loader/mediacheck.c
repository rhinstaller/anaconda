/* simple program to check implanted md5sum in an iso 9660 image   */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <newt.h>

#include "md5.h"

#define APPDATA_OFFSET 883
#define SIZE_OFFSET 84

#define MAX(x, y)  ((x > y) ? x : y)
#define MIN(x, y)  ((x < y) ? x : y)

/* number of sectors to ignore at end of iso when computing sum */
#define SKIPSECTORS 15

typedef void (*checkCallback)(void *, long long offset);

struct progressCBdata {
    newtComponent scale;
    newtComponent label;
};

#ifdef TESTING
#define _(x) (x)
#else
#include "lang.h"
#endif

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
int checkmd5sum(int isofd, char *mediasum, char *computedsum, 
		checkCallback cb, void *cbdata) {
    int nread;
    int i;
    int appdata_start_offset, appdata_end_offset;
    int nattempt;
    unsigned int bufsize = 32768;
    unsigned char md5sum[16];
    unsigned int len;
    unsigned char *buf;
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
	if (cb)
	    cb(cbdata, offset);
    }

    if (cb)
	cb(cbdata, isosize);
    
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

int doMediaCheck(int isofd, char *mediasum, char *computedsum, long long *isosize) {
    struct progressCBdata data;
    newtComponent t, f, scale, label;
    int rc;
    int llen;

    if (parsepvd(isofd, mediasum, isosize) < 0) {
	newtWinMessage(_("Error"), _("OK"),
		       _("Unable to read the disc checksum from the "
			 "primary volume descriptor.  This probably "
			 "means the disc was created without adding the "
			 "checksum."));
	return -1;
    }

    newtCenteredWindow(35, 6, _("Media Check"));
    t = newtTextbox(1, 1, 24, 3, NEWT_TEXTBOX_WRAP);
    newtTextboxSetText(t, _("Checking media now..."));
    llen = strlen(_("Checking media now..."));

    label = newtLabel(llen+2, 1, "-");
    f = newtForm(NULL, NULL, 0);
    newtFormAddComponent(f, t);
    scale = newtScale(3, 3, 25, *isosize);
    newtFormAddComponent(f, scale);

    newtDrawForm(f);
    newtRefresh();

    data.scale = scale;
    data.label = label;

    rc = checkmd5sum(isofd, mediasum, computedsum, readCB, &data);

    newtFormDestroy(f);
    newtPopWindow();

    return rc;
}

int mediaCheckFile(char *file) {
    int isofd;
    int rc;
    char *result;
    unsigned char mediasum[33], computedsum[33];
    char tmpstr[256];
    long long isosize;
    newtComponent t, f;

    isofd = open(file, O_RDONLY);

    if (isofd < 0) {
	newtWinMessage(_("Error"), _("OK"), _("Unable to find install image "
					      "%s"), file);
	return -1;
    }

    rc = doMediaCheck(isofd, mediasum, computedsum, &isosize);

    close(isofd);

    /*    printf("isosize = %lld\n", isosize); 
	  printf("%s\n%s\n", mediasum, computedsum);*/

    if ( rc == 0)
	result = _("FAIL.\n\nIt is not recommended to use this media.");
    else if (rc > 0)
	result = _("PASS.\n\nIt is OK to install from this media.");
    else
	result = _("NA.\n\nNo checksum information available, unable to verify media.");

    newtCenteredWindow(60, 10, _("Media Check Result"));
    t = newtTextbox(4, 1, 52 , 5, NEWT_TEXTBOX_WRAP);
    snprintf(tmpstr, sizeof(tmpstr), _("The media check is complete, the "
				       "result is: %s"), result);
    newtTextboxSetText(t, tmpstr);
    f = newtForm(NULL, NULL, 0);
    newtFormAddComponent(f, t);
    newtFormAddComponent(f, newtButton(26, 6, _("OK")));

    newtRunForm(f);
    newtFormDestroy(f);
    newtPopWindow();
    return rc;
}

#ifdef TESTING

int main(int argc, char **argv) {
    int rc;

    if (argc < 2) {
	printf("Usage: checkisomd5 <isofilename>\n\n");
	exit(1);
    }

    newtInit();
    newtCls();
    rc = mediaCheckFile(argv[1]);
    newtFinished();
}
#endif

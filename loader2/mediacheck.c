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

#include "log.h"

#define APPDATA_OFFSET 883
#define SIZE_OFFSET 84

#define MAX(x, y)  ((x > y) ? x : y)
#define MIN(x, y)  ((x < y) ? x : y)

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
int parsepvd(int isofd, char *mediasum, int *skipsectors, long long *isosize, int *isostatus) {
    unsigned char buf[2048];
    unsigned char buf2[512];
    unsigned char tmpbuf[512];
    int skipfnd, md5fnd, isostatusfnd;
    unsigned int loc;
    long long offset;
    unsigned char *p;

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

    *isostatus = 0;

    md5fnd = 0;
    skipfnd = 0;
    isostatusfnd = 0;
    loc = 0;
    while (loc < 512) {
	if (!strncmp(buf2 + loc, "ISO MD5SUM = ", 13)) {

	    /*	    logMessage("Found ISO MD5SUM"); */

	    /* make sure we dont walk off end */
	    if ((loc + 32) > 511)
		return -1;

	    memcpy(mediasum, buf2 + loc + 13, 32);
	    mediasum[32] = '\0';
	    md5fnd = 1;

	    logMessage("MD5SUM -> %s", mediasum);

	    loc += 45;
	    for (p=buf2+loc; loc < 512 && *p != ';'; p++, loc++);
	} else if (!strncmp(buf2 + loc, "SKIPSECTORS = ", 14)) {
	    char *errptr;

	    /* make sure we dont walk off end */
	    if ((loc + 14) > 511)
		return -1;

	    /*	    logMessage("Found SKIPSECTORS"); */
	    loc = loc + 14;
	    for (p=tmpbuf; loc < 512 && buf2[loc] != ';'; p++, loc++)
		*p = buf2[loc];

	    *p = '\0';

	    /*	    logMessage("SKIPSECTORS -> |%s|", tmpbuf); */

	    *skipsectors = strtol(tmpbuf, &errptr, 10);
	    if (errptr && *errptr) {
		logMessage("Could not parse |%s|", errptr);
 	        return -1;
	    } else {
		logMessage("skipsectors = %d", *skipsectors);
 	        skipfnd = 1;
	    }

	    for (p=buf2+loc; loc < 512 && *p != ';'; p++, loc++);
	} else if (!strncmp(buf2 + loc, "RHLISOSTATUS=1", 14)) {
	    *isostatus = 1;
	    isostatusfnd = 1;
	    logMessage("isostatus = 1");
	} else if (!strncmp(buf2 + loc, "RHLISOSTATUS=0", 14)) {
	    *isostatus = 0;
	    isostatusfnd = 1;
	    logMessage("isostatus = 0");
	} else {
	    loc++;
	}

	if ((skipfnd & md5fnd) & isostatusfnd)
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
int checkmd5sum(int isofd, char *mediasum, char *computedsum, 
		checkCallback cb, void *cbdata) {
    int nread;
    int i;
    int appdata_start_offset, appdata_end_offset;
    int nattempt;
    int skipsectors;
    int isostatus;
    unsigned int bufsize = 32768;
    unsigned char md5sum[16];
    unsigned int len;
    unsigned char *buf;
    long long isosize, offset, pvd_offset, apoff;
    MD5_CTX md5ctx;

    isostatus = 0;
    if ((pvd_offset = parsepvd(isofd, mediasum, &skipsectors, &isosize, &isostatus)) < 0)
	return -1;

    /* rewind, compute md5sum */
    lseek(isofd, 0L, SEEK_SET);

    MD5_Init(&md5ctx);

    offset = 0;
    apoff = pvd_offset + APPDATA_OFFSET;

    buf = malloc(bufsize * sizeof(unsigned char));
    while (offset < isosize - skipsectors*2048) {
	nattempt = MIN(isosize - skipsectors*2048 - offset, bufsize);

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

int doMediaCheck(int isofd, char *descr, char *mediasum, char *computedsum, long long *isosize, int *isostatus) {
    struct progressCBdata data;
    newtComponent t, f, scale, label;
    int rc;
    int dlen;
    int llen;
    int skipsectors;
    char tmpstr[1024];

    if (parsepvd(isofd, mediasum, &skipsectors, isosize, isostatus) < 0) {
	newtWinMessage(_("Error"), _("OK"),
		       _("Unable to read the disc checksum from the "
			 "primary volume descriptor.  This probably "
			 "means the disc was created without adding the "
			 "checksum."));
	return -1;
    }

    if (descr)
	snprintf(tmpstr, sizeof(tmpstr), _("Checking \"%s\"..."), descr);
    else
	snprintf(tmpstr, sizeof(tmpstr), _("Checking media now..."));

    dlen = strlen(tmpstr);
    if (dlen > 65)
	dlen = 65;

    newtCenteredWindow(dlen+8, 6, _("Media Check"));
    t = newtTextbox(1, 1, dlen+4, 3, NEWT_TEXTBOX_WRAP);

    newtTextboxSetText(t, tmpstr);
    llen = strlen(tmpstr);

    label = newtLabel(llen+1, 1, "-");
    f = newtForm(NULL, NULL, 0);
    newtFormAddComponent(f, t);
    scale = newtScale(3, 3, dlen, *isosize);
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

int mediaCheckFile(char *file, char *descr) {
    int isofd;
    int rc;
    int isostatus;
    char *result;
    unsigned char mediasum[33], computedsum[33];
    char tmpstr[512];
    char descrstr[256];
    long long isosize;
    newtComponent t, f;

    isofd = open(file, O_RDONLY);

    if (isofd < 0) {
	newtWinMessage(_("Error"), _("OK"), _("Unable to find install image "
					      "%s"), file);
	return -1;
    }

    isostatus = 0;
    rc = doMediaCheck(isofd, descr, mediasum, computedsum, &isosize, &isostatus);
    close(isofd);

    if (rc == 0) {
	result = _("FAIL.\n\n"
		   "The image which was just tested has errors. "
		   "This could be due to a "
		   "corrupt download or a bad disc.  "
		   "If applicable, please clean the disc "
		   "and try again.  If this test continues to fail you "
		   "should not continue the install.");

	logMessage("mediacheck: %s (%s) FAILED", file, descr);
	logMessage("value of isostatus iso flag is %d", isostatus);
    } else if (rc > 0) {
	result = _("PASS.\n\nIt is OK to install from this media.");
	logMessage("mediacheck: %s (%s) PASSED", file, descr);
	logMessage("value of isostatus iso flag is %d", isostatus);
    } else {
	result = _("NA.\n\nNo checksum information available, unable to verify media.");
	logMessage("mediacheck: %s (%s) has no checksum info", file, descr);
    }

    newtCenteredWindow(60, 20, _("Media Check Result"));
    t = newtTextbox(4, 1, 56, 18, NEWT_TEXTBOX_WRAP);
    if (descr)
	snprintf(descrstr, sizeof(descrstr),
		 _("of the image:\n\n%s\n\n"), descr);
    else
	descrstr[0] = '\0';

    snprintf(tmpstr, sizeof(tmpstr), _("The media check %sis complete, and "
				       "the result is: %s\n"), descrstr, result);
    newtTextboxSetText(t, tmpstr);
    f = newtForm(NULL, NULL, 0);
    newtFormAddComponent(f, t);
    newtFormAddComponent(f, newtButton(26, 15, _("OK")));

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
    rc = mediaCheckFile(argv[1], "TESTING");
    newtFinished();
}
#endif

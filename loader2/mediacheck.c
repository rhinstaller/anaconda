/* simple program to check implanted md5sum in an iso 9660 image   */
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
#include <newt.h>
#include <libcheckisomd5.h>

#include "lang.h"
#include "log.h"

struct progressCBdata {
    newtComponent scale;
    newtComponent label;
};

static void readCB(void *co, long long pos, long long total) {
    struct progressCBdata *data = co;
    char tickmark[2] = "-";
    char * ticks = "-\\|/";

    newtScaleSet(data->scale, pos / total);
    *tickmark = ticks[(pos / total) % 5];

    newtLabelSetText(data->label, tickmark);
    newtRefresh();
}

int doMediaCheck(char *file, char *descr) {
    struct progressCBdata data;
    newtComponent t, f, scale, label;
    int rc;
    int dlen;
    int llen;
    char tmpstr[1024];

    if (access(file, R_OK) < 0) {
	newtWinMessage(_("Error"), _("OK"), _("Unable to find install image "
					      "%s"), file);
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
    scale = newtScale(3, 3, dlen, 100);
    newtFormAddComponent(f, scale);

    newtDrawForm(f);
    newtRefresh();

    data.scale = scale;
    data.label = label;

    rc = mediaCheckFile(file, readCB, &data);

    newtFormDestroy(f);
    newtPopWindow();

    if (rc == -1)
	newtWinMessage(_("Error"), _("OK"),
		       _("Unable to read the disc checksum from the "
			 "primary volume descriptor.  This probably "
			 "means the disc was created without adding the "
			 "checksum."));

    return rc;
}

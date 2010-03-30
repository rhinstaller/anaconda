/*
 * simple program to check implanted md5sum in an iso 9660 image
 *
 * Copyright (C) 2001, 2005  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s): Michael Fulbright <msf@redhat.com>
 *            Dustin Kirkland <dustin.kirkland@gmail.com>
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <newt.h>
#include <libcheckisomd5.h>

#include "../isys/log.h"

#include "lang.h"
#include "windows.h"

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
	snprintf(tmpstr, sizeof(tmpstr), _("Checking \"%s\"."), descr);
    else
	snprintf(tmpstr, sizeof(tmpstr), _("Checking media."));

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

    rc = mediaCheckFile(file, progressCallback, &data);

    newtFormDestroy(f);
    newtPopWindow();

    if (rc == ISOMD5SUM_CHECK_NOT_FOUND) {
	logMessage(WARNING, "mediacheck: %s (%s) has no checksum info", file, descr);
	newtWinMessage(_("Error"), _("OK"),
		       _("Unable to find the checksum in the "
			 "image.  This probably "
			 "means the disc was created without adding the "
			 "checksum."));
    } else if (rc == ISOMD5SUM_FILE_NOT_FOUND) {
        logMessage(WARNING, "mediacheck: %s (%s) open failed", file, descr);
        newtWinMessage(_("Error"), _("OK"),
                       _("Unable to open the image."));
    } else if (rc == ISOMD5SUM_CHECK_FAILED) {
        logMessage(ERROR, "mediacheck: %s (%s) FAILED", file, descr);
        newtWinMessage(_("Error"), _("OK"),
                       _("The image which was just tested has errors. "
                         "This could be due to a "
                         "corrupt download or a bad disc.  "
                         "If applicable, please clean the disc "
                         "and try again.  If this test continues to fail you "
                         "should not continue the install."));
    } else if (rc == ISOMD5SUM_CHECK_PASSED) {
        logMessage(INFO, "mediacheck: %s (%s) PASSED", file, descr);
        newtWinMessage(_("Success"), _("OK"),
                       _("The image which was just tested was successfully "
                         "verified.  It should be OK to install from this "
                         "media.  Note that not all media/drive errors can "
                         "be detected by the media check."));
    }


    return rc;
}

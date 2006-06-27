/*
 * windows.c - simple popup windows used by the loader
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <errno.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

#include "windows.h"

void winStatus(int width, int height, char * title, char * text, ...) {
    newtComponent t, f;
    char * buf = NULL;
    va_list args;

    va_start(args, text);

    if (vasprintf(&buf, text, args) != -1) {
        newtCenteredWindow(width, height, title);

        t = newtTextbox(1, 1, width - 2, height - 2, NEWT_TEXTBOX_WRAP);
        newtTextboxSetText(t, buf);
        f = newtForm(NULL, NULL, 0);

        free(buf);

        newtFormAddComponent(f, t);

        newtDrawForm(f);
        newtRefresh();
        newtFormDestroy(f);
    }

    va_end(args);
}


void scsiWindow(const char * driver) {
    winStatus(40, 3, _("Loading SCSI driver"),
        _("Loading %s driver..."), driver);
}

/* vim:set shiftwidth=4 softtabstop=4: */

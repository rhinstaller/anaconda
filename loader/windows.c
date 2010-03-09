/*
 * windows.c - simple popup windows used by the loader
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002  Red Hat, Inc.
 * All rights reserved.
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
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <errno.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <math.h>

#include "../isys/log.h"

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
        _("Loading %s driver"), driver);
}

int progressCallback(void *pbdata, long long pos, long long total) {
    struct progressCBdata *data = pbdata;
    char tickmark[2] = "-";
    char *ticks = "-\\|/";
    int x = ceil(pos * 100.0 / total);

    newtScaleSet(data->scale, x);
    *tickmark = ticks[x % 4];

    newtLabelSetText(data->label, tickmark);
    newtRefresh();
    return 0;
}

struct progressCBdata *winProgressBar(int width, int height, char *title, char *text, ...) {
    struct progressCBdata *data;
    char *buf = NULL;
    va_list args;
    int llen;
    newtComponent t, f, scale, label;

    va_start(args, text);

    if (vasprintf(&buf, text, args) != -1) {
        va_end(args);
        newtCenteredWindow(width, height, title);
        t = newtTextbox(1, 1, width - 2, height - 2, NEWT_TEXTBOX_WRAP);
        newtTextboxSetText(t, buf);
        llen = strlen(buf);
        free(buf);
        label = newtLabel(llen + 1, 1, "-");
        f = newtForm(NULL, NULL, 0);
        newtFormAddComponent(f, t);
        scale = newtScale(3, 3, width - 6, 100);
        newtFormAddComponent(f, scale);
        newtDrawForm(f);
        newtRefresh();

        if ((data = malloc(sizeof(struct progressCBdata))) == NULL) {
            logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
            abort();
        }

        data->scale = scale;
        data->label = label;
        return data;
    }

    return NULL;
}

/* vim:set shiftwidth=4 softtabstop=4: */

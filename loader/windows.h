/*
 * windows.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
 */

#ifndef _WINDOWS_H_
#define _WINDOWS_H_

#include <newt.h>

#include "lang.h"

void winStatus(int width, int height, char * title, char * text, ...);
void scsiWindow(const char * driver);

#define errorWindow(String) \
	newtWinMessage(_("Error"), _("OK"), String, strerror (errno));

typedef void (*progressCB) (void *pbdata, long long offset, long long total);

struct progressCBdata {
    newtComponent scale;
    newtComponent label;
};

int progressCallback(void *pbdata, long long pos, long long total);
struct progressCBdata *winProgressBar(int width, int height, char *title, char *text, ...);

#endif /* _WINDOWS_H_ */

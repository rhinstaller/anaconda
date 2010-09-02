/*
 * method.h
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

#ifndef H_METHOD
#define H_METHOD

#include "loader.h"
#include "windows.h"

/* method identifiers, needs to match struct installMethod order in loader.c */
enum {
    METHOD_CDROM,
    METHOD_HD,
    METHOD_NFS,
    METHOD_URL
};

struct installMethod {
    char * name;
    int network;
    enum deviceType type;
    int (*prompt)(struct loaderData_s *loaderData);
    int (*findExtras)(struct loaderData_s *loaderData);
};

int readStampFileFromIso(char *file, char **descr, char **timestamp);
void queryIsoMediaCheck(char * isoDir);

int getFileFromBlockDevice(char *device, char *path, char * dest);

int unpackCpioBall(char * ballPath, char * rootDir);
void copyUpdatesImg(char * path);
void copyProductImg(char * path);

#endif

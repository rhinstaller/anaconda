/*
 * lang.h
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

#ifndef ISYS_LANG_H
#define ISYS_LANG_H

#include "stubs.h"

/* define ask johnsonm@redhat.com where this came from */
#define KMAP_MAGIC 0x8B39C07F
#define KMAP_NAMELEN 40         /* including '\0' */

struct kmapHeader {
    int magic;
    int numEntries;
};
        
struct kmapInfo {
    int size;
    char name[KMAP_NAMELEN];
};

int loadKeymap(gzFile stream);
int isysLoadFont(void);
int isysLoadKeymap(char * keymap);
int isysSetUnicodeKeymap(void);

#endif

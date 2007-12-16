/*
 * mapshdr.c
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

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

#include "../isys/lang.h"

int main(int argc, char ** argv) {
    struct kmapHeader h;
    struct kmapInfo info;
    int i, x;
    struct stat sb;
    char * chptr;

    h.magic = KMAP_MAGIC;
    h.numEntries = argc - 1;
    x = write(1, &h, sizeof(h));

    for (i = 1; i < argc; i++) {
	if (stat(argv[i], &sb)) {
	    fprintf(stderr, "stat error for %s: %s\n", argv[i], 
			strerror(errno));
	    exit(1);
	}

	memset(info.name, 0, KMAP_NAMELEN);
	strncpy(info.name, argv[i], KMAP_NAMELEN - 1);

	chptr = info.name + strlen(info.name) - 1;
	while (*chptr != '.') *chptr-- = '\0';
	*chptr = '\0';

	info.size = sb.st_size;
	x = write(1, &info, sizeof(info));
    }

    return 0;
}

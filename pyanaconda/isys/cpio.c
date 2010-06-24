/*
 * cpio.c
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

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "cpio.h"

int installCpioFile(gzFile fd, char * cpioName, char * outName, int inWin) {
    struct cpioFileMapping map;
    int rc;
    const char * failedFile;

    if (outName) {
	map.archivePath = cpioName;
	map.fsPath = outName;
	map.mapFlags = CPIO_MAP_PATH;
    }

    rc = myCpioInstallArchive(fd, outName ? &map : NULL, 1, NULL, NULL, 
			    &failedFile);

    if (rc || access(outName, R_OK)) {
	return -1;
    }

    return 0;
}

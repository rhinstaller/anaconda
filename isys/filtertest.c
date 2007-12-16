/*
 * filtertest.c
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

#include <stdio.h>
#include <fcntl.h>
#include <stdarg.h>

#include "cpio.h"

void warn() {
}

void logMessage(char * text, ...) {
    va_list args;
    
    va_start(args, text);
    
    vfprintf(stderr, text, args);
    fprintf(stderr, "\n");

    va_end(args);
}

int main(int argc, char ** argv) {
    gzFile in, out; 
    int rc;

    if (argc < 3) {
	fprintf(stderr, "bad arguments!\n");
	return 1;
    }

    in = gunzip_open(argv[1]);
    if (!in) {
	fprintf(stderr, "failed to open %s\n", argv[1]);
    }

    out = gzip_dopen(1);

    rc = myCpioFilterArchive(in, out, argv + 2);

    gzip_close(out);

    return rc;
}

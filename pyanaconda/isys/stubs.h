/*
 * stubs.h
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

/* we use gzlib when linked against dietlibc, but otherwise, we should use
   zlib.  it would make more sense to do the defines in the other direction, 
   but that causes symbol wackiness because both gunzip_open and gzip_open in
   gzlib are gzopen from zlib
*/

#ifndef ISYS_STUB
#define ISYS_STUB

#ifndef GZLIB
#include <zlib.h>

#define gunzip_open(x) gzopen(x, "r")
#define gunzip_dopen gzdopen(x, "r")
#define gunzip_close gzclose
#define gunzip_read gzread
#define gzip_write gzwrite
#define gzip_open(x, y, z) gzopen(x, "w")

#else
#include "gzlib/gzlib.h"

#endif

#endif

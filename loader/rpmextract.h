/*
   File name: rpmextract.h
   Date:      2009/09/16
   Author:    msivak

   Copyright (C) 2009 Red Hat, Inc.

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation; either version 2 of the
   License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program. If not, see <http://www.gnu.org/licenses/>.
*/


#ifndef __RPMEXTRACT_H__
#define __RPMEXTRACT_H__

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#define EXIT_BADDEPS 4
#define BUFFERSIZE 1024

/* both filter functions return 0 - match, 1 - match not found */
typedef int (*filterfunc)(const char* name, const struct stat *fstat, void *userptr);
typedef int (*dependencyfunc)(const char* depends, void *userptr);

int explodeRPM(const char* file,
               filterfunc filter,
               dependencyfunc provides,
               dependencyfunc deps,
               void* userptr);

#endif

/* end of rpmextract.h */

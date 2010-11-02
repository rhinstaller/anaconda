/*
 * unpack.h - libarchive helper functions
 *
 * Copyright (C) 2010  Red Hat, Inc.
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
 * Author(s): David Cantrell <dcantrell@redhat.com>
 */

#ifndef UNPACK_H
#define UNPACK_H

#include <archive.h>
#include "rpmextract.h"

int unpack_init(struct archive **);
int unpack_members_and_finish(struct archive *, char *,
                              filterfunc, void *);
int unpack_archive_file(char *, char *);

#endif

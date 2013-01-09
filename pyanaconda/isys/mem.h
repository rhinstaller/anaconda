/*
 * mem.h
 *
 * Copyright (C) 2010-2011  Red Hat, Inc.
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
 * Red Hat Author(s): Ales Kozumplik <akozumpl@redhat.com>
 *                    David Cantrell <dcantrell@redhat.com>
 */

#ifndef _MEM_H_
#define _MEM_H_

#include <glib.h>

#define MEMINFO "/proc/meminfo"

guint64 totalMemory(void);

#endif /* _MEM_H_ */

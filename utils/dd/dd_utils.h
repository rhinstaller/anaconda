/*
 * Copyright (C) 2013  Red Hat, Inc.
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
 * Author: Martin Sivak <msivak@redhat.com>
 */
#ifndef _DD_UTILS_H_
#define _DD_UTILS_H_

/* DD extract flags */
enum {
    dup_nothing = 0,
    dup_modules = 1,
    dup_firmwares = 2,
    dup_binaries = 4,
    dup_libraries = 8
} _dup_extract;

#endif /* _DD_UTILS_H_ */

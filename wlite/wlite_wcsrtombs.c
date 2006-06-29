/*
 * $Id$
 *
 * Copyright (C) 2003  Red Hat, Inc.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Original Author: Adrian Havill <havill@redhat.com>
 *
 * Contributors:
 */

#include "wlite_config.h"   // wchar_t, NULL, size_t

#include "wlite_wchar.h"    // prototypes
#include "wlite_wctype.h"
#include "wlite_stdlib.h"

size_t
wlite_wcsrtombs(char *dst, const wchar_t **src, size_t n, wlite_mbstate_t *ps) {
    static wlite_mbstate_t internal = { 0 };
    size_t stored = 0;

    while (n != 0) {
        char utf[7] = { 0 };
        const wchar_t *wcs = *src;
        int length = wlite_wcrtomb(utf, *wcs++, ps == NULL ? &internal : ps);

        *src = wcs;
        if (length == -1) return (size_t) -1;
        if (((long) n - (long) length) < 0) {
            wlite_memcpy_(dst, utf, n);
            n = 0;
        }
        else {
            wlite_memcpy_(dst, utf, length);
            n -= (size_t) length;
        }
        if (*dst == '\0') break;
        else {
            dst += (size_t) length;
            stored += (size_t) length;
        }
    }
    return stored;
}

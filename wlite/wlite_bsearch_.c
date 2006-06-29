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

void *
wlite_bsearch_(const void *key, const void *base, size_t n, size_t size,
               wlite_cmp_t_ cmp) {
    const char *left = (const char *) base;
    size_t right = n;

    while (right != 0) {
        const char *const middle = left + size * (right / 2);
        const int result = (*cmp)(key, middle);

        if (result < 0) {
            right = right / 2;
        }
        else if (result > 0) {
            left = middle + size;
            right -= right / 2 + 1;
        }
        else return (void *) middle;
    }
    return NULL;
}

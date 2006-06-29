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

extern const wlite_map_t_ wlite_case[]; extern const size_t wlite_case_n;
extern const wlite_map_t_ wlite_fixw[]; extern const size_t wlite_fixw_n;

wlite_wint_t
wlite_towctrans(wlite_wint_t c, wlite_wctrans_t desc) {
    const wchar_t upper[] = L"ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const wchar_t lower[] = L"abcdefghijklmnopqrstuvwxyz";
    const wchar_t *ptr;
#if WLITE_EXTENSIONS
    wlite_map_t_ key, *map;
    const void *base;
    size_t nelem, size;
#endif

    switch (desc) {
    case wlite_toupper_:
        ptr = wlite_wcschr(lower, c);
        if (ptr != NULL) {
            return upper[ptr - lower];
        }
        return c;
    case wlite_tolower_:
        ptr = wlite_wcschr(upper, c);
        if (ptr != NULL) {
            return lower[ptr - upper];
        }
        return c;
#if WLITE_EXTENSIONS
    case wlite_tocase_:
        key.from = c;
        base = wlite_case;
        nelem = wlite_case_n;
        size = sizeof(wlite_map_t_);
        map = wlite_bsearch_(&key, base, nelem, size, wlite_map_t_cmp_);
        return map == NULL ? c : map->to;
    case wlite_tokata_: // TODO
        key.from = c;
        size = sizeof(wlite_map_t_);
        return c;
    case wlite_tonorm_:
        key.from = c;
        base = wlite_fixw;
        nelem = wlite_fixw_n;
        size = sizeof(wlite_map_t_);
        map = wlite_bsearch_(&key, base, nelem, size, wlite_map_t_cmp_);
        return map == NULL ? c : map->to;
#endif
    }
    return WLITE_WEOF;
}

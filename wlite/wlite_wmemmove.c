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

wchar_t *
wlite_wmemmove(wchar_t *s1, const wchar_t *s2, size_t n) {
    wchar_t *sc1 = (wchar_t *) s1;
    const wchar_t *sc2 = (const wchar_t *) s2;

    if (sc2 < sc1 && sc1 < sc2 + n) {
        for (sc1 += n, sc2 += n; n != 0; n--) {
            *--sc1 = *--sc2;
        }
    }
    else while (n != 0) {
        *sc1++ = *sc2++;
        --n;
    }
    return s1;
}

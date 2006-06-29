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

#include "wlite_config.h"

int
wlite_map_t_cmp_(const void *x, const void *y) {
    const wlite_map_t_ *a = x, *b = y;

    if (a->from < b->from) return -1;
    if (a->from > b->from) return +1;
    return 0;
}

int
wlite_wc_t_cmp_(const void *x, const void *y) {
    const wlite_wc_t_ *a = (const wlite_wc_t_ *) x;
    const wlite_wc_t_ *b = (const wlite_wc_t_ *) y;

    if (*a < *b) return -1;
    if (*a > *b) return +1;
    return 0;
}

int
wlite_locale_cmp_(const void *x, const void *y) {
    const char *a = x, *b = y;

    if (a == NULL) a = "";
    if (b == NULL) b = "";
    do {
        if (*a == '*' || *b == '*') break;
        if (*a < *b) return -1;
        if (*a > *b) return +1;
    } while (*a++ != '\0' && *b++ != '\0');
    return 0;
}

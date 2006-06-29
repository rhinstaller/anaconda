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

#include <limits.h>  // INT_MIN, ULONG_MAX, LONG_MIN
#include "wlite_config.h"   // wchar_t, NULL, size_t

#include "wlite_wchar.h"    // prototypes
#include "wlite_wctype.h"

static wlite_wint_t
next_char(const wchar_t **s) {
    wlite_wint_t c = **s;

#if WLITE_EXTENSIONS
    while (c != L'\0') {
        if (!wlite_iswctype(c, wlite_ignore_)) break;
        c = *++*s;
    }
#endif
    if (c != L'\0') {
        ++*s;
        c = wlite_towctrans(c, wlite_tolower_);
#if WLITE_EXTENSIONS
        c = wlite_towctrans(c, wlite_tocase_);
        c = wlite_towctrans(c, wlite_tonorm_);
#endif
    }
    return c;
}

long long
wlite_widetoll_(const wchar_t *s, wchar_t **endptr, unsigned base) {
    static const wchar_t *const valid = L"0123456789abcdefghijklmnopqrstuvwxyz";
    const size_t base_max = 36;
    const wchar_t *ptr = s, *digit, *start;
    wlite_wint_t c;
    wchar_t sign;
    long long i = 0;

    do {
        c = next_char(&ptr);
        if (c == L'\0') break;
    } while (wlite_iswctype(c, wlite_space_));
    if (c != L'-' && c != L'+') {
        if (ptr != s) {
            --ptr;
        }
        sign = L'+';
    }
    else sign = c;
    if (base > base_max) {
        if (endptr) {
            *endptr = (wchar_t *) s;
        }
        return 0;
    }
    else if (base != 0) {
        if (base == 16 && ptr[0] == L'0' && (ptr[1] == L'x')) {
            ptr += 2;
        }
    }
    else {
        if (ptr[0] != L'0') {
            base = 10;
        }
        else if (ptr[1] == L'x') {
            base = 16;
            ptr += 2;
        }
        else base = 8;
    }
    start = ptr;
    while ((digit = wlite_wmemchr(valid, c = next_char(&ptr), base)) != NULL) {
        i *= base;
        i += (unsigned) (digit - valid);
        if ((i > ULONG_MAX) || (i < LONG_MIN)) break;
    }
    if (start == ptr) {
        if (endptr != NULL) {
            *endptr = (wchar_t *) s;
        }
        return 0;
    }
    if (sign == L'-') {
        i = -i;
    }
    if (endptr != NULL) {
        if (digit == NULL && c != L'\0') {
            ptr--;
        }
        *endptr = (wchar_t *) ptr;
    }
    return i;
}

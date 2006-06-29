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

#include <errno.h>   // errno, EILSEQ, ERANGE

#include "wlite_config.h"   // wchar_t, NULL, size_t

#include "wlite_wchar.h"    // prototypes
#include "wlite_wctype.h"
#include "wlite_stdlib.h"

static const long wlite_invalid = -1;
static const long wlite_incomplete = -2;

#if WLITE_READ_6_BYTE_UTF8_SURROGATE && WLITE_XBMP_CHAR
static int
is_surrogate_hi(wchar_t u) { return u >= 0xD800 && u <= 0xDBFF; }

static int
is_surrogate_lo(wchar_t u) { return u >= 0xDC00 && u <= 0xDFFF; }

static wchar_t
make_utc_from_surrogates(wchar_t hi, wchar_t lo) {
    wchar_t u = 0;

    u += (hi - 0xD800) *  0x400;
    u += lo - 0xDC00 + 0x10000;
    return u;
}
#endif

static int
is_plane_0(wchar_t u) { return (u + 1) > 0x0000 && (u - 1) < 0xFFFF; }

static void
make_surrogates(unsigned long u, wchar_t *hi, wchar_t *lo) {
    if (hi != NULL)
        *hi = (u - 0x10000) / 0x400 + 0xD800;
    if (lo != NULL)
        *lo = (u - 0x10000) % 0x400 + 0xDC00;
}

static int
is_tail(uint8_t c) { return (c & 0xC0) == 0x80; }

static long
get_utc(const unsigned char **utf8, size_t *length) {
    long u = 0;
    const uint8_t *s = NULL;

    if (*length == 0) return wlite_incomplete;
    s = *utf8;
    if (s[0] < 128) {
        /* HEAD/TAIL pattern: 0zzzzzzz
         * ... ASCII is just ASCII. Ain't UTF-8 wonderful?
         */

        u |= (*s++ & 0x7F) <<  0;
        *length -= 1;
    }
    else if ((s[0] & 0xE0) == 0xC0) {
        /* HEAD/TAIL pattern: 110yyyyy 10zzzzzz
         * ... most probably a European character or fancy dingbat/sym if we're
         * here
         */

        if (*length < 2) return wlite_incomplete;
        if (!is_tail(s[1])) return wlite_invalid;
        u |= (*s++ & 0x1F) <<  6;
        u |=  *s++ & 0x3F  <<  0;
        *length -= 2;
        if (u < 0x0080) u = wlite_invalid;
    }
    else if ((s[0] & 0xF0) == 0xE0) {
        /* HEAD/TAIL/TAIL pattern: 1110xxxx 10yyyyyy 10zzzzzz
         * ... most probably a CJK character, but sometimes Euro/Asian/African.
         */

        if (*length < 3) return wlite_incomplete;
        if (!is_tail(s[1]) || !is_tail(s[2])) return wlite_invalid;
        u |= (*s++ & 0x0F) << 12;
        u |= (*s++ & 0x3F) <<  6;
        u |= (*s++ & 0x3F) <<  0;
        *length -= 3;
        if (u < 0x0800) u = wlite_invalid;

#   if WLITE_READ_6_BYTE_UTF8_SURROGATE && WLITE_XBMP_CHAR
        if (is_surrogate_hi(u)) {
            /* XXX: see the note below regarding four byte patterns
             *
             * if you're here with the debugger then you should probably check
             * your favorite character encoding converter for brain-damage.
             */

            size_t length_copy = *length;  /* save from recursion */
            const unsigned char *s_copy = s;

            long u1 = u;
            long u2 = get_utc(&s_copy, &length_copy);

            if (u2 == wlite_incomplete) return u2;
            else if (is_surrogate_lo(u2)) {
                u = make_utc_from_surrogates(u1, u2);
                *length -= 3;
                s += 3;
            }
        }
#   endif
    }
    else if ((s[0] & 0xF8) == 0xF0) {
        /* HEAD/TAIL/TAIL/TAIL bit pattern: 11110www 10xxxxxx 10yyyyyy 10zzzzzz
         * ... most probably a freak CJK character and the string is testing
         * ... Unicode conformance. Either that or you're attempting to process
         * ... Klingon.
         *
         * XXX: if you're here with the debugger and you're working with
         * real-world text, it's probably suspect (I doubt you have any fonts
         * to represent the characters in this range anyway)
         */

        if (*length < 4) return wlite_incomplete;  // incomplete
        if (!is_tail(s[1]) || !is_tail(s[2]) || !is_tail(s[3]))
            return wlite_invalid;
        u |= (*s++ & 0x07) << 18;
        u |= (*s++ & 0x3F) << 12;
        u |= (*s++ & 0x3F) <<  6;
        u |= (*s++ & 0x3F) <<  0;
        *length -= 4;
        if (u <= 0xFFFF) {
            u = wlite_invalid;
        }
    }
    else {
        /* we either got a five or six byte UTF-8 sequence, a "decapitated"
         * (all tail with no head byte-- sometimes raw Latin-1 slipped in a
         * UTF-8 string) UTF-8 sequence, or we got 0xFE or 0xFF in the byte
         * stream (always illegal in UTF-8-- which means these two can be used
         * as private non-exported sentinals in applications. Did I mention
         * that UTF-8 is wonderful?)
         */

        u = wlite_invalid;
        while (*length != 0 && (is_tail(*s) || *s >= 0xF8)) {
            --*length;
            ++s;
        }
    }
    *utf8 = s;
    return u;
}

size_t
wlite_mbrtowc(wchar_t *c, const char *s, size_t n, wlite_mbstate_t *ps) {
    static wlite_mbstate_t internal = { 0 };
    size_t consumed = 0, remaining = n;
    const unsigned char *utf8 = (const unsigned char *) s;
    long u = 0;

    if (ps == NULL)
        ps = &internal;
    if (s != NULL) {
        u = get_utc(&utf8, &remaining);
        if (u == wlite_incomplete) {
            ps->flags_ |=  WLITE_MBSTATE_INCOMPLETE_;
            ps->flags_ &= ~WLITE_MBSTATE_ERROR_;
            return (size_t) -2;
        }
        else if (u == wlite_invalid) {
            ps->flags_ &= ~WLITE_MBSTATE_INCOMPLETE_;
            ps->flags_ |=  WLITE_MBSTATE_ERROR_;
            errno = EILSEQ;
            return (size_t) -1;
        }
        else {
            ps->wcout_ = 0;
            if (c != NULL) {
                if ((ps->flags_ & WLITE_MBSTATE_SURROGATE_) && !is_plane_0(u)) {
                    wchar_t hi, lo;

                    make_surrogates(u, &hi, &lo);
                    /* XXX: Std C does not allow writing more than one wide
                     * character to c; this is a non-standard extension for
                     * internal API use.
                     */

                    c[0] = (wchar_t) hi;
                    c[1] = (wchar_t) lo;
                    ps->wcout_ = 2;
                }
                else {
                    *c = (wchar_t) u;
                    ps->wcout_ = 1;
                }
            }
            if (u == 0) {
                wlite_0_mbstate_(ps);
                return 0;
            }
            consumed = n - remaining;
        }
    }
    else if (s == NULL) {
        if (ps->flags_ & WLITE_MBSTATE_INCOMPLETE_) {
            errno = EILSEQ;
            return (size_t) -1;
        }
        else {
            wlite_0_mbstate_(ps);
            return WLITE_MBS_SHIFT_STATES_;
        }
    }
    return consumed;
}

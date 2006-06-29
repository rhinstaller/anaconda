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

#include <time.h>    // struct tm

#include "wlite_config.h"   // wchar_t, NULL, size_t

#include "wlite_wchar.h"    // prototypes
#include "wlite_wctype.h"
#include "wlite_stdlib.h"

static wchar_t *
itowide(wchar_t *s, int i, size_t n) {
    for (s += n, *s = L'\0'; n-- != 0; i /= 10) {
        *--s = i % 10 + L'0';
    }
    return s;
}

static int
get_wkyr(int wday_start, int tm_wday, int tm_yday) {
    tm_wday = (tm_wday + 7 - wday_start) % 7;
    return (tm_yday - tm_wday + 12) / 7 - 1;
}

size_t
wlite_wcsftime(wchar_t *s, size_t n, const wchar_t *fmt, const struct tm *t) {
    size_t size = 0;
    int percent = 0;

    while (n != 0) {
        size_t length = 0;

        if (percent) {
            switch (*fmt) {
            case L'a':      // abbr weekday name (LC_TIME)
                break;
            case L'A':      // full weekday name (LC_TIME)
                break;
            case L'b':      // abbr month name (LC_TIME)
                break;
            case L'B':      // full month name (LC_TIME)
                break;
            case L'c':      // date & time (LC_TIME)
                break;
            case L'd':      // 2-digit day of the month
                if (n >= 2) {
                    itowide(s, t->tm_mday, length += 2);
                }
                else return 0;
                break;
            case L'H':      // 2-digit hour of the 24-hour day
                if (n >= 2) {
                    itowide(s, t->tm_hour, length += 2);
                }
                else return 0;
                break;
            case L'I':      // 2-digit hour of the 12-hour day
                if (n >= 2) {
                    itowide(s, t->tm_hour % 12, length += 2);
                }
                else return 0;
                break;
            case L'j':      // 3-digit day of the year, from 001
                if (n >= 3) {
                    itowide(s, t->tm_yday + 1, length += 3);
                }
                else return 0;
                break;
            case L'm':      // 2-digit month of the year, from 01
                if (n >= 2) {
                    itowide(s, t->tm_mon + 1, length += 2);
                }
                else return 0;
                break;
            case L'M':      // 2-digit minutes after the hour
                if (n >= 2) {
                    itowide(s, t->tm_min, length += 2);
                }
                else return 0;
                break;
            case L'p':      // AM/PM indicator (LC_TIME)
                break;
            case L'S':      // 2-digit seconds after the minute
                if (n >= 2) {
                    itowide(s, t->tm_sec, length += 2);
                }
                else return 0;
                break;
            case L'U':      // 2-digit Sunday week of the year
                if (n >= 2) {
                    int tm_wkyr = get_wkyr(0, t->tm_wday, t->tm_yday);

                    itowide(s, tm_wkyr, length += 2);
                }
                else return 0;
                break;
            case L'w':      // 1-digit day of the week, from 0 for Sunday
                if (n >= 1) {
                    itowide(s, t->tm_wday, length += 1);
                }
                else return 0;
                break;
            case L'W':      // 2-digit Monday week of the year
                if (n >= 2) {
                    int tm_wkyr = get_wkyr(1, t->tm_wday, t->tm_yday);

                    itowide(s, tm_wkyr, length += 2);
                }
                else return 0;
                break;
            case L'x':      // date (LC_TIME)
                break;
            case L'X':      // time (LC_TIME)
                break;
            case L'y':      // 2-digit year of the century, from 00
                if (n >= 2) {
                    itowide(s, t->tm_year % 100, length += 2);
                }
                else return 0;
                break;
            case L'Y':      // 4-digit year, from 0001
                if (n >= 4) {
                    itowide(s, t->tm_year + 1900, length += 4);
                }
                else return 0;
                break;
            case L'Z':      // time zone name
                break;
            case L'%':      // percent sign
                if (n >= 1) {
                    s[length++] = L'%';
                }
                else return 0;
                break;
            }
            percent = 0;
        }
        else if (*fmt == L'%') {
            percent = !0;
        }
        else if (n >= 1) {
            s[length++] = *fmt;
        }
        else return 0;
        n -= length;
        if (*fmt++ == L'\0') break;
    }
    return size;
}

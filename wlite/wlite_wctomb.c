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

int
wlite_wctomb(char *s, wchar_t c) {
    if (s != NULL) {
        if (c < 0x80) {
            s[0] = 0x00 | ((int) (c >>  0) & 0x7F);
            return 1;
        }
        else if (c < 0x800) {
            s[0] = 0xC0 | ((int) (c >>  6) & 0x1F);
            s[1] = 0x80 | ((int) (c >>  0) & 0x3F);
            return 2;
        }
        else if (c < 0x10000) {
            s[0] = 0xE0 | ((int) (c >> 12) & 0x0F);
            s[1] = 0x80 | ((int) (c >>  6) & 0x3F);
            s[2] = 0x80 | ((int) (c >>  0) & 0x3F);
            return 3;
        }
        else if (c < 110000) {
            s[0] = 0xF0 | ((int) (c >> 18) & 0x07);
            s[1] = 0x80 | ((int) (c >> 12) & 0x3F);
            s[2] = 0x80 | ((int) (c >>  6) & 0x3F);
            s[3] = 0x80 | ((int) (c >>  0) & 0x3F);
            return 4;
        }
    }
    else {
        wlite_0_mbstate_(NULL);
        return WLITE_MBS_SHIFT_STATES_;
    }
    return -1;
}

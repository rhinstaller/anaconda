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

wlite_wctrans_t
wlite_wctrans(const char *name) {
    if (wlite_strcmp_(name, "toupper") == 0) return wlite_toupper_;
    if (wlite_strcmp_(name, "tolower") == 0) return wlite_tolower_;
#if WLITE_EXTENSIONS
    if (wlite_strcmp_(name, "katakana") == 0) return wlite_tokata_;
    if (wlite_strcmp_(name, "fixwidth") == 0) return wlite_tonorm_;
#endif
    return (wlite_wctrans_t) 0;
}

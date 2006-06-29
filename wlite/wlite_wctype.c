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

wlite_wctype_t
wlite_wctype(const char *name) {
    if (wlite_strcmp_(name, "alnum")  == 0) return wlite_alnum_;
    if (wlite_strcmp_(name, "alpha")  == 0) return wlite_alpha_;
    if (wlite_strcmp_(name, "blank")  == 0) return wlite_blank_;
    if (wlite_strcmp_(name, "cntrl")  == 0) return wlite_cntrl_;
    if (wlite_strcmp_(name, "digit")  == 0) return wlite_digit_;
    if (wlite_strcmp_(name, "graph")  == 0) return wlite_graph_;
    if (wlite_strcmp_(name, "lower")  == 0) return wlite_lower_;
    if (wlite_strcmp_(name, "print")  == 0) return wlite_print_;
    if (wlite_strcmp_(name, "punct")  == 0) return wlite_punct_;
    if (wlite_strcmp_(name, "space")  == 0) return wlite_space_;
    if (wlite_strcmp_(name, "upper")  == 0) return wlite_upper_;
    if (wlite_strcmp_(name, "xdigit") == 0) return wlite_xdigit_;
#if WLITE_EXTENSIONS
    if (wlite_strcmp_(name, "ambiw")  == 0) return wlite_ambi_;
    if (wlite_strcmp_(name, "fullw")  == 0) return wlite_full_;
    if (wlite_strcmp_(name, "halfw")  == 0) return wlite_half_;
    if (wlite_strcmp_(name, "han")    == 0) return wlite_han_;
    if (wlite_strcmp_(name, "hangul") == 0) return wlite_hangul_;
    if (wlite_strcmp_(name, "hira")   == 0) return wlite_hira_;
    if (wlite_strcmp_(name, "ident1") == 0) return wlite_id1_;
    if (wlite_strcmp_(name, "identn") == 0) return wlite_id2ton_;
    if (wlite_strcmp_(name, "ignore") == 0) return wlite_ignore_;
    if (wlite_strcmp_(name, "kana")   == 0) return wlite_kana_;
    if (wlite_strcmp_(name, "kata")   == 0) return wlite_kata_;
#endif
    return (wlite_wctype_t) 0;
}

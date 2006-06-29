/*
 * $Package: wlite $ $Version: 0.8.1 $
 *    a tiny <wctype.h> for embedded & freestanding C
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

#ifndef WLITE_WCTYPE_H_
#define WLITE_WCTYPE_H_

#include "wlite_config.h"

#if !defined WLITE_WEOF
    #define WLITE_WEOF           ((wchar_t)-1)
#endif

#if !defined WLITE_WINT_T_
    #define WLITE_WINT_T_
    typedef wchar_t wlite_wint_t;

    #if WLITE_REDEF_STDC
        #define wint_t     wlite_wint_t
    #endif
#endif

typedef enum {
    wlite_alnum_ = 1,   /* "alnum" */
    wlite_alpha_,       /* "alpha" */
    wlite_blank_,       /* "blank" */
    wlite_cntrl_,       /* "cntrl": extended to support Unicode 3.x */
    wlite_digit_,       /* "digit" */
    wlite_graph_,       /* "graph" */
    wlite_lower_,       /* "lower" */
    wlite_print_,       /* "print" */
    wlite_punct_,       /* "punct": extended to support Unicode 3.x */
    wlite_space_,       /* "space" */
    wlite_upper_,       /* "upper" */
    wlite_xdigit_,      /* "xdigit" */
#if WLITE_EXTENSIONS
    wlite_ambi_,        /* "ambiw": !0 if the width is CJK ambiguous */
    wlite_ascii_,       /* "ascii": BSD/SVID extension; !0 if 7-bit char */
    wlite_full_,        /* "fullw": !0 if east asian full-width variant */
    wlite_half_,        /* "halfw": !0 if east asian half-width variant */
    wlite_han_,         /* "han": !0 if a CJKV kanxi/kanji/hanja */
    wlite_hangul_,      /* "hangul": !0 if a korean hangul/jamo */
    wlite_id1_,         /* "ident1": !0 if ok as 1st char of an identifier */
    wlite_id2ton_,      /* "identn": !0 if ok as 2..nth char of identifier */
    wlite_ignore_,      /* "ignore": !0 if irrelevant for collation */
    wlite_hira_,        /* "hira": !0 if a japanese hiragana */
    wlite_kana_,        /* "kana": !0 is a japanese hiragana or katakana */
    wlite_kata_,        /* "kata": !0 if a japanese katakana */
#endif
} wlite_wctype_t;

typedef enum {
    wlite_toupper_ = 1, /* "toupper" */
    wlite_tolower_,     /* "tolower" */
#if WLITE_EXTENSIONS
    wlite_tocase_,      /* "foldcase": eliminates case differences */
    wlite_tokata_,      /* "katakana": converts japanese hiragana to katakana */
    wlite_tonorm_,      /* "fixwidth": normalizes fullwidth & halfwidth forms */
#endif
} wlite_wctrans_t;

int             wlite_iswctype (wlite_wint_t,wlite_wctype_t);
wlite_wint_t    wlite_towctrans(wlite_wint_t,wlite_wctrans_t);
wlite_wctrans_t wlite_wctrans (const char*);
wlite_wctype_t  wlite_wctype   (const char*);

/*****************************************************************************/

#if WLITE_REDEF_STDC
    /* don't let these header file load again by loading them now, because it
     * will redefine our macros
     */

    #define iswalnum(c)  wlite_iswctype((c),wlite_alnum_)
    #define iswalpha(c)  wlite_iswctype((c),wlite_alpha_)
    #define iswcntrl(c)  wlite_iswctype((c),wlite_cntrl_)
    #define iswdigit(c)  wlite_iswctype((c),wlite_digit_)
    #define iswgraph(c)  wlite_iswctype((c),wlite_graph_)
    #define iswlower(c)  wlite_iswctype((c),wlite_lower_)
    #define iswprint(c)  wlite_iswctype((c),wlite_print_)
    #define iswpunct(c)  wlite_iswctype((c),wlite_punct_)
    #define iswspace(c)  wlite_iswctype((c),wlite_space_)
    #define iswupper(c)  wlite_iswctype((c),wlite_upper_)
    #define iswxdigit(c) wlite_iswctype((c),wlite_xdigit_)
    #define towlower(c)  wlite_towctrans((c),wlite_tolower_)
    #define towupper(c)  wlite_towctrans((c),wlite_toupper_)

    #define iswctype   wlite_iswctype
    #define towctrans  wlite_towctrans
    #define wctrans    wlite_wctrans
    #define wctype     wlite_wctype

    #define wctrans_t  wlite_wctrans_t
    #define wctype_t   wlite_wctype_t
#endif

#endif

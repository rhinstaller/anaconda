/*
 * $Package: wlite $ $Version: 0.8.1 $
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

#ifndef WLITE_CONFIG_H_
#define WLITE_CONFIG_H_

/*
 * if set to non-zero, utf8 versions of wcwidth in the library must be called
 * by their proper identifiers, which always begin with a "wlite_" prefix (e.g.
 * "wlite_wcwidth"). If it is zero, calls to some wide character functions in
 * <wchar.h>, <wctype.h>, and <stdlib.h> will be redefined by the preprocessor
 * to use this libraries equivalents, if available.
 */
#ifndef WLITE_REDEF_STDC
#define WLITE_REDEF_STDC                  !0
#endif

/* if the below is zero then wide family functions will not work on wchar_t
 * values > 0xFFFF.
 *
 * XXX: a BIG savings in data memory is obtained by setting to zero
 */
#ifndef WLITE_XBMP_CHAR
#define WLITE_XBMP_CHAR                   !0
#endif

/*
 * when set to non-zero, will squeeze four byte UTF-8 representing U-10000 to
 * U-10FFFF into two wide chars via surrogates and back.
 *
 * XXX: this setting is forced to non-zero if WLITE_XBMP_CHAR is zero
 */
#ifndef WLITE_GENERATE_SURROGATES
#define WLITE_GENERATE_SURROGATES          0
#endif

/*
 * if set to non-zero, <wctype.h> related classification and transformation
 * functions will be augmented (in a portable way) to support transformations
 * and classifications useful for CJK UTF-8 users.
 *
 * XXX: a savings in data memory is obtained by setting to zero
 */
#ifndef WLITE_EXTENSIONS
#define WLITE_EXTENSIONS                  !0
#endif

/*
 * if WLITE_AMBI_LOCALE is non-zero, characters that are considered to have
 * ambiguous width will be resolved by examining the locale settings of the
 * environment; if the environment is a CJKV locale, ambiguous characters will
 * have a monospace width of two-- otherwise, their width will be one.
 *
 * XXX: a savings in data memory is obtained if WLITE_AMBI_LOCALE is zero
 * XXX: if WLITE_AMBI_LOCALE is zero, WLITE_LC_ALL determines ambiguous width
 */
#ifndef WLITE_AMBI_LOCALE
#define WLITE_AMBI_LOCALE                 !0
#endif

/*
 * if WLITE_ENVIRONMENT is zero, wlite_*() functions will be sensitive to the
 * setting of WLITE_LC_ALL. if WLITE_ENVIRONMENT's positive, wlite_*() functions
 * will be sensitive to the value returned by setlocale(). if WLITE_ENVIRONMENT
 * is negative, wlite_*() functions will be sensitive to environment variables
 * such as "LC_COLLATE", "LC_TIME", and "LC_CTYPE"; LANG and LC_ALL settings are
 * ignored.
 *
 * XXX: a non-positive value results in non-standard behavior, but for
 *      performance/space reasons (setlocale() is often a very expensive
 *      function & environment variables may not be available or reliable on
 *      certain hosts), environmental variables or hard-coding the
 *      locale may be used.
 */
#ifndef WLITE_ENVIRONMENT
#define WLITE_ENVIRONMENT                 +1
#endif

/*
 * WLITE_LC_ALL specifies the locale that wlite_*() functions are affected by.
 * 
 * XXX: WLITE_LC_ALL is ignored if WLITE_ENVIRONMENT is non-zero
 */
#ifndef WLITE_LC_ALL
#define WLITE_LC_ALL                       C
#endif

/*
 * not really legal as you're not using the shortest possible sequence to
 * generate a Unicode character, but some overly-literal encoding converters do
 * generate them. 6 byte utf-8 hi/lo surrogate combinations are never written;
 * characters >U+FFFF are always written with 4 utf-8 bytes.
 *
 * XXX: WLITE_READ_6_BYTE_UTF8_SURROGATE is ignored if WLITE_XBMP_CHAR is zero
 */
#ifndef WLITE_READ_6_BYTE_UTF8_SURROGATE
#define WLITE_READ_6_BYTE_UTF8_SURROGATE  !0
#endif

/*
 * the width of U+FFFD depends on the substitute glyph (if any) used to
 * represent it. If you use "?" (ala Netscape and Mozilla), or a middle dot or
 * small filled rectangle (ala Windows), the width is one. If you use something
 * like the replacement glyphs <http://crl.nmsu.edu/~mleisher/lr.html> or the
 * ideograph replacement character (U+3013) (which is convenient because it
 * already exists in most legacy CJK fonts), or a square with four hex symbols
 * compressed in it, the width is probably two.
 */
#ifndef WLITE_FFFD_WIDTH
#define WLITE_FFFD_WIDTH                   2
#endif

/*****************************************************************************/

#include <stddef.h>

/* XXX: it seems that gcc either has problems with bit-shift operators if
 * WLITE_BITARRAY_N_ > 32 and the architecture is 32 bits, so keep
 * WLITE_ARRAY_* bits <= 32 to avoid using 64-bit types (i.e. "uint64_t")
 * with "<<" and ">>".
 */
#include <stdint.h>
#define WLITE_BITARRAY_N_                 32U
typedef uint32_t wlite_bitarray_t_;
#if WLITE_XBMP_CHAR
typedef wchar_t wlite_wc_t_;
#else
typedef unsigned short wlite_wc_t_;
#endif

typedef int (*wlite_cmp_t_)(const void*,const void*);
typedef struct { wlite_wc_t_ from, to; } wlite_map_t_;

int wlite_map_t_cmp_(const void*, const void*);
int wlite_wc_t_cmp_(const void*, const void*);
int wlite_locale_cmp_(const void*, const void*);
long long wlite_widetoll_(const wchar_t*,wchar_t**,unsigned);
int wlite_strcmp_(const char*, const char*);
char *wlite_memcpy_(char*,const char*,size_t);
void *wlite_bsearch_(const void*,const void*,size_t,size_t,wlite_cmp_t_);
void wlite_0_mbstate_(void*);

#define WLITE_ID2STR_(identifier) #identifier

#define WLITE_MBS_SHIFT_STATES_ 0

#define WLITE_MBSTATE_INCOMPLETE_ 1
#define WLITE_MBSTATE_ERROR_      2
#define WLITE_MBSTATE_SURROGATE_  4

#if WLITE_ENVIRONMENT
    #if WLITE_ENVIRONMENT > 0
        #include <locale.h>
        #define WLITE_GET_LOCALE(category) setlocale((category),NULL)
    #else
        #include <stdlib.h>
        #define WLITE_GET_LOCALE(category) getenv(#category)
    #endif
#elif defined WLITE_LC_ALL
    #define WLITE_GET_LOCALE(category) WLITE_ID2STR_(WLITE_LC_ALL)
#else
    #define WLITE_GET_LOCALE(category) NULL
#endif

#define WLITE_LOCALE_CMP_(category, value) \
            wlite_locale_cmp_(WLITE_GET_LOCALE(category),(value))

#define WLITE_IS_CJK_(category) ( \
               WLITE_LOCALE_CMP_((category),"zh*") == 0 \
            || WLITE_LOCALE_CMP_((category),"ja*") == 0 \
            || WLITE_LOCALE_CMP_((category),"ko*") == 0 \
        )
#define WLITE_IS_POSIX_(category) ( \
               WLITE_LOCALE_CMP_((category),"C") == 0 \
            || WLITE_LOCALE_CMP_((category),"POSIX") == 0 \
        )

#if __STDC_VERSION__ >= 199409L
    #include <wchar.h>  /* WCHAR_MAX, WCHAR_MIN */

    #if WLITE_XBMP_CHAR && WCHAR_MAX < WLITE_WCHAR_MAX
        #error WLITE_XBMP_CHAR is set & wide characters are only two bytes wide
    #endif
#endif

#endif

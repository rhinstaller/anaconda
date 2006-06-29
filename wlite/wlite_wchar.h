/*
 * $Package: wlite $ $Version: 0.8.1 $
 *    a tiny <wchar.h> for embedded & freestanding C
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

#ifndef WLITE_WCHAR_H_
#define WLITE_WCHAR_H_

#include "wlite_config.h"

/*****************************************************************************/

#include <stddef.h>   /* wchar_t, size_t, NULL */
#include <time.h>     /* struct tm */

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

#define WLITE_MB_MAX_LEN     6
#if WLITE_ALLOW_6_BYTE_UTF8_SURROGATE
#   define WLITE_MB_CUR_LEN  6
#else
#   define WLITE_MB_CUR_LEN  4
#endif

#if WLITE_XBMP_CHAR
    #define WLITE_WCHAR_MAX      0x10FFFF
#else
    #define WLITE_WCHAR_MAX      0x00FFFF
#endif
#define WLITE_WCHAR_MIN      0x000000

typedef struct { int flags_, wcout_; } wlite_mbstate_t;

wlite_wint_t   wlite_btowc    (int);
int            wlite_mblen    (const char*,size_t);
size_t         wlite_mbrlen   (const char*,size_t,wlite_mbstate_t*);
size_t         wlite_mbrtowc  (wchar_t*,const char*,size_t,wlite_mbstate_t*);
int            wlite_mbsinit  (const wlite_mbstate_t*);
size_t         wlite_mbsrtowcs(wchar_t*,const char**,size_t,wlite_mbstate_t*);
size_t         wlite_mbstowcs (wchar_t*,const char*,size_t);
int            wlite_mbtowc   (wchar_t*,const char*,size_t);
size_t         wlite_wcrtomb  (char*,wchar_t,wlite_mbstate_t*);
wchar_t*       wlite_wcscat   (wchar_t*,const wchar_t*);
wchar_t*       wlite_wcschr   (const wchar_t*,wchar_t);
int            wlite_wcscmp   (const wchar_t*,const wchar_t*);
int            wlite_wcscoll  (const wchar_t*,const wchar_t*);
wchar_t*       wlite_wcscpy   (wchar_t*,const wchar_t*);
size_t         wlite_wcscspn  (const wchar_t*,const wchar_t*);
wchar_t*       wlite_wcsdup   (const wchar_t*);
size_t         wlite_wcsftime (wchar_t*,size_t,const wchar_t*,const struct tm*);
size_t         wlite_wcslen   (const wchar_t*);
wchar_t*       wlite_wcsncat  (wchar_t*,const wchar_t*,size_t);
int            wlite_wcsncmp  (const wchar_t*,const wchar_t*,size_t);
wchar_t*       wlite_wcsncpy  (wchar_t*,const wchar_t*,size_t);
wchar_t*       wlite_wcspbrk  (const wchar_t*,const wchar_t*);
wchar_t*       wlite_wcsrchr  (const wchar_t*,wchar_t);
size_t         wlite_wcsrtombs(char*,const wchar_t**,size_t,wlite_mbstate_t*);
size_t         wlite_wcsspn   (const wchar_t *,const wchar_t *);
wchar_t*       wlite_wcsstr   (const wchar_t*,const wchar_t*);
wchar_t*       wlite_wcstok   (wchar_t*,const wchar_t*,wchar_t**);
double         wlite_wcstod   (const wchar_t*,wchar_t**);
long           wlite_wcstol   (const wchar_t*,wchar_t**,int);
size_t         wlite_wcstombs (char*,const wchar_t*,size_t);
unsigned long  wlite_wcstoul  (const wchar_t*,wchar_t**,int);
int            wlite_wcswidth (const wchar_t*,size_t);
size_t         wlite_wcsxfrm  (wchar_t*,const wchar_t*,size_t);
int            wlite_wctob    (wlite_wint_t);
int            wlite_wctomb   (char*,wchar_t);
int            wlite_wcwidth  (wchar_t);
wchar_t*       wlite_wmemchr  (const wchar_t*,wchar_t,size_t);
int            wlite_wmemcmp  (const wchar_t*,const wchar_t*,size_t);
wchar_t*       wlite_wmemcpy  (wchar_t*,const wchar_t*,size_t);
wchar_t*       wlite_wmemmove (wchar_t*,const wchar_t*,size_t);
wchar_t*       wlite_wmemset  (wchar_t*,wchar_t,size_t);

/*****************************************************************************/

#if WLITE_REDEF_STDC
    /* don't let these header file load again by loading them now, because it
     * will redefine our macros
     */

    #include <limits.h>     /* MB_LEN_MAX */
    #include <stdlib.h>     /* MB_CUR_MAX */

    #undef MB_CUR_LEN
    #undef MB_MAX_LEN
    #undef WCHAR_MAX
    #undef WCHAR_MIN

    #define MB_CUR_LEN WLITE_MB_CUR_LEN
    #define MB_MAX_LEN WLITE_MB_MAX_LEN
    #define WCHAR_MAX  WLITE_WCHAR_MAX
    #define WCHAR_MIN  WLITE_WCHAR_MIN

    #define btowc      wlite_btowc
    #define mblen      wlite_mblen
    #define mbrlen     wlite_mbrlen
    #define mbrtowc    wlite_mbrtowc
    #define mbsinit    wlite_mbsinit
    #define mbstowcs   wlite_mbstowcs
    #define mbsrtowcs  wlite_mbsrtowcs
    #define mbtowc     wlite_mbtowc
    #define wcrtomb    wlite_wcrtomb
    #define wcscat     wlite_wcscat
    #define wcschr     wlite_wcschr
    #define wcscmp     wlite_wcscmp
    #define wcscoll    wlite_wcscoll
    #define wcscpy     wlite_wcscpy
    #define wcscspn    wlite_wcscspn
    #define wcsdup     wlite_wcsdup
    #define wcsftime   wlite_wcsftime
    #define wcspbrk    wlite_wcspbrk
    #define wcslen     wlite_wcslen
    #define wcsncat    wlite_wcsncat
    #define wcsncmp    wlite_wcsncmp
    #define wcsncpy    wlite_wcsncpy
    #define wcsrchr    wlite_wcsrchr
    #define wcsrtombs  wlite_wcsrtombs 
    #define wcsspn     wlite_wcsspn    
    #define wcsstr     wlite_wcsstr    
    #define wcstok     wlite_wcstok    
    #define wcstod     wlite_wcstod
    #define wcstol     wlite_wcstol
    #define wcstombs   wlite_wcstombs
    #define wcstoul    wlite_wcstoul
    #define wcswcs     wlite_wcsstr    
    #define wcswidth   wlite_wcswidth
    #define wcsxfrm    wlite_wcsxfrm
    #define wctob      wlite_wctob
    #define wctomb     wlite_wctomb
    #define wcwidth    wlite_wcwidth
    #define wmemchr    wlite_wmemchr
    #define wmemcmp    wlite_wmemcmp
    #define wmemcpy    wlite_wmemcpy
    #define wmemmove   wlite_wmemmove
    #define wmemset    wlite_wmemset

    #define mbstate_t  wlite_mbstate_t
#endif

#endif

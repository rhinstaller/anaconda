/*
 * $Package: wlite $ $Version: 0.8.1 $
 *    a mb/wc subset for embedded & freestanding C
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

#ifndef WLITE_STDLIB_H_
#define WLITE_STDLIB_H_

#include "wlite_config.h"

/*****************************************************************************/

#include <stddef.h>   /* wchar_t, size_t, NULL */

#define WLITE_MB_MAX_LEN     6
#if WLITE_ALLOW_6_BYTE_UTF8_SURROGATE
#   define WLITE_MB_CUR_LEN  6
#else
#   define WLITE_MB_CUR_LEN  4
#endif

int            wlite_mblen    (const char*,size_t);
size_t         wlite_mbstowcs (wchar_t*,const char*,size_t);
int            wlite_mbtowc   (wchar_t*,const char*,size_t);
size_t         wlite_wcstombs (char*,const wchar_t*,size_t);
int            wlite_wctomb   (char*,wchar_t);

/*****************************************************************************/

#if WLITE_REDEF_STDC
    /* don't let these header file load again by loading them now, because it
     * will redefine our macros
     */

    #include <limits.h>     /* MB_LEN_MAX */
    #include <stdlib.h>     /* MB_CUR_MAX */

    #undef MB_CUR_LEN
    #undef MB_MAX_LEN

    #define MB_CUR_LEN WLITE_MB_CUR_LEN
    #define MB_MAX_LEN WLITE_MB_MAX_LEN

    #define mblen      wlite_mblen
    #define mbstowcs   wlite_mbstowcs
    #define mbtowc     wlite_mbtowc
    #define wcstombs   wlite_wcstombs
    #define wctomb     wlite_wctomb
#endif

#endif

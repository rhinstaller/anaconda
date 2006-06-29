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

extern const wlite_bitarray_t_ wlite_wide[];
extern const wlite_bitarray_t_ wlite_ambi[];

int
wlite_wcwidth(wchar_t c) {
    size_t index = c / WLITE_BITARRAY_N_;
    int bit = c % WLITE_BITARRAY_N_, is_wide = 0, width = -1;
#if WLITE_AMBI_LOCALE
    int is_ambiguous;
#endif

    if (c == L'\0') return 0;  // by wcwidth() definition; ignore table
#if !WLITE_XBMP_CHAR
        if (c > 0xFFFF) return -1;
#endif
    is_wide = (wlite_wide[index] >> bit) & 1;
#if WLITE_AMBI_LOCALE
    is_ambiguous = (wlite_ambi[index] >> bit) & 1;
    if (is_ambiguous)
       is_wide = WLITE_IS_CJK_(LC_CTYPE);
#endif

    switch ((long) c) {
        /* ea_array[] can tell us whether a character is 1 or 2 cells wide, but
         * it can't tell us what are zero or variable cells wide. This ugly
         * select handles those non-default cases.
         */

    //*************************************************************************

    case    0xFDD0 ...   0xFDEF:       // non-character code points */
    case  0x00FFFE ... 0x00FFFF:

#if WLITE_XBMP_CHAR
    case  0x01FFFE ... 0x01FFFF:
    case  0x02FFFE ... 0x02FFFF:
    case  0x03FFFE ... 0x03FFFF:
    case  0x04FFFE ... 0x04FFFF:
    case  0x05FFFE ... 0x05FFFF:
    case  0x06FFFE ... 0x06FFFF:
    case  0x07FFFE ... 0x07FFFF:
    case  0x08FFFE ... 0x08FFFF:
    case  0x09FFFE ... 0x09FFFF:
    case  0x0AFFFE ... 0x0AFFFF:
    case  0x0BFFFE ... 0x0BFFFF:
    case  0x0CFFFE ... 0x0CFFFF:
    case  0x0DFFFE ... 0x0DFFFF:
    case  0x0EFFFE ... 0x0EFFFF:
    case  0x0FFFFE ... 0x0FFFFF:
    case  0x10FFFE ... 0x10FFFF:
#endif
        width = -1;
        break;

    //*************************************************************************

    case 0xFFFC:                       // U+FFFC = object substitution
        /* XXX: no way to know what is going to be substituted for U+FFFC,
         * but it will probably be replaced with a substitution, of which the
         * width will be known and added to the string containing U+FFFC.
         * If this is the case you may want to change the below to 0.
         */

        width = -1;
        break;

    //*************************************************************************

    case 0xAD:                         // U+00AD = SHY (Soft Hyphen)
    case 0x1806:                       // U+1806 = Mongolian soft hyphen
        /* XXX: some implementations may always ignore soft-hyphens or always
         * render them. return -1 if they are sometimes rendered and sometimes
         * not depending on the context.
         */
#if 0
        width = 0;
        break;
#endif
        /*FALLTHRU*/

    //*************************************************************************

    default:
        if (wlite_iswctype((c), wlite_cntrl_)) {
            if (c == 0x08 || c == 0x7F) {  // U+0008 = \b = BS (Backspace; ^H)
                /* XXX: wcwidth is not capable of return negative widths
                 * because -1 is reserved for "unknown"
                 */
                width = -1;
                break;
            }
            else if (c == 0x09) {          // U+0009 = \t = HT (Tab; ^I)
                /* XXX: TABs are usually 1 to 8 spaces, but we have no context
                 * as to where the cursor is.
                 */

                width = -1;
                break;
            }
            else if (c == 0x1A) {          // U+001A = SUB (^Z)
                /* FIXME: handle this like U+FFFD or U+FFFC? Unicode hints that
                 * it should be treated like U+FFFD, but it IS a control
                 * character, implying that an action occurs and it's not mapped
                 * to any one glyph, similar to U+FFFC.
                 *
                 * BUT, In real life, Ctrl-Z is usually used like Unix's "stdin
                 * eof" Ctrl-D-- that is, a "stdin eof" for MS-DOS. It can be
                 * found at the end of older DOS text files, so treat it as
                 * width 0.
                 */

                width = -1;
                break;
            }
        }
        width = is_wide ? 2 : 1;
        break;

    //*************************************************************************

    case 0xFFFD:                       // U+FFFD = replacement character
        width = WLITE_FFFD_WIDTH;
        break;
    }
    return width;
}

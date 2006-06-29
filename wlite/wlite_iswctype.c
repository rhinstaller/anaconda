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

extern const wlite_wc_t_ wlite_punct[]; extern const size_t wlite_punct_n;
extern const wlite_bitarray_t_ wlite_ambi[];

int
wlite_iswctype(wlite_wint_t c, wlite_wctype_t desc) {
    wlite_wc_t_ wc = (wlite_wc_t_) c;
    wlite_map_t_ key;
    void *found;
    const void *base;
    size_t nelem, size;

    key.from = wc;
    switch (desc) {
    case wlite_alnum_:
        return wlite_iswctype(c,wlite_alpha_) || wlite_iswctype(c,wlite_digit_);
    case wlite_alpha_:
        return wlite_iswctype(c,wlite_lower_) || wlite_iswctype(c,wlite_upper_);
    case wlite_blank_:
        return c == L' ' || c == L'\t' || c == (wchar_t) 0x3000;
    case wlite_cntrl_:
        switch (c) {
        case 0x00 ... 0x1F:                // ASCII C0 control characters
        case 0x7F:                         // U+007F = DEL (Delete)
        case 0x80 ... 0x9F:                // Latin-1 C1 control characters

        case 0x180B ... 0x180D:            // Mongolian variation selectors
        case 0x200C ... 0x200D:            // Join controls are zero width
        case 0x200E ... 0x200F:            // BiDi control ltr & rtl marks, etc.
        case 0x202A ... 0x202E:
        case 0x2060 ... 0x2063:            // word joiner; invisible separator
        case 0x2064 ... 0x2069:
        case 0x206A ... 0x206F:            // inhibit swapping; nominal digit
        case 0x2028:                       // U+2028 = line separator
        case 0x2029:                       // U+2029 = paragraph separator
        case 0xFE00 ... 0xFE0F:            // variation selectors
        case 0xFEFF:                       // U+FEFF = ZWNBSP or BOM
        case 0xFFF0 ... 0xFFF8:
        case 0xFFF9 ... 0xFFFB:            // interlinear annotation (jpn ruby)
#if WLITE_XBMP_CHAR
        case  0x0E0000 ... 0x0E0FFF:       // language & other meta tags
#endif
            return !0;
        }
        break;
    case wlite_digit_:
        return c >= L'0' && c <= L'9';
    case wlite_graph_:
        return wlite_iswctype(c,wlite_alnum_) || wlite_iswctype(c,wlite_punct_);
    case wlite_lower_:
        if (WLITE_IS_POSIX_(LC_CTYPE)) return c >= L'a' && c <= L'z';
        return c >= L'a' && c <= L'z'; // XXX: Unicode's too complicated
    case wlite_print_:
        return wlite_iswctype(c,wlite_graph_) || wlite_iswctype(c,wlite_space_);
    case wlite_punct_:
        base = wlite_punct;
        nelem = wlite_punct_n;
        size = sizeof(wlite_wc_t_);
        found = wlite_bsearch_(&wc, base, nelem, size, wlite_wc_t_cmp_);
        return found != NULL;
    case wlite_space_:
        if (!WLITE_IS_POSIX_(LC_CTYPE))  {
            switch (c) {
            case 0x85:
            case 0xA0:                // NO-BREAK SPACE
            case 0x1680:              // OGHAM SPACE
            case 0x2000 ... 0x200A:   // EN QUAD .. HAIR SPACE
            case 0x2028:              // LINE SEPARATOR
            case 0x2029:              // PARAGRAPH SEPARATOR
            case 0x202F:              // NARROW NO-BREAK SPACE
            case 0x3000:              // IDEOGRAPHIC SPACE
                return !0;
            }
        }
        return wlite_wcschr(L" \t\n\r\v\f", (wchar_t) c) != NULL;
    case wlite_upper_:
        if (WLITE_IS_POSIX_(LC_CTYPE)) return c >= L'A' && c <= L'Z';
        return c >= L'A' && c <= L'Z'; // XXX: Unicode's too complicated
    case wlite_xdigit_:
        return (c >= L'a' && c <= L'f') || (c >= L'A' && c <= L'F')
               || wlite_iswctype(c,wlite_digit_);
#if WLITE_EXTENSIONS
    case wlite_ambi_:
#if WLITE_AMBI_LOCALE
        return (wlite_ambi[c/WLITE_BITARRAY_N_] >> (c%WLITE_BITARRAY_N_)) & 1;
#else
        return 0;
#endif
    case wlite_ascii_:            // SVID/BSD extension
        return c < (wlite_wint_t) 0x80;
    case wlite_full_:
        return (c >= (wchar_t) 0xFF01 && c <= (wchar_t) 0xFF5E)
               || (c >= (wchar_t) 0xFFE0 && c <= (wchar_t) 0xFFE6);
    case wlite_half_:
        return (c >= (wchar_t) 0xFF61 && c <= (wchar_t) 0xFFDC)
               || (c >= (wchar_t) 0xFFE8 && c <= (wchar_t) 0xFFEE);
    case wlite_ignore_:
        switch (c) {
        case 0x0000 ... 0x0008:  // <control>..<control>
        case 0x000E ... 0x001F:  // <control>..<control>
        case 0x007F ... 0x0084:  // <control>..<control>
        case 0x0086 ... 0x009F:  // <control>..<control>
        case 0x06DD:             // ARABIC END OF AYAH
        case 0x070F:             // SYRIAC ABBREVIATION MARK
        case 0x180B ... 0x180D:  // MONGOLIAN FREE VARIATION SELECTOR
        case 0x180E:             // MONGOLIAN VOWEL SEPARATOR
        case 0x200C ... 0x200F:  // ZERO WIDTH NON-JOINER..RIGHT-TO-LEFT MARK
        case 0x202A ... 0x202E:  // LTR EMBEDDING..RTL OVERRIDE
        case 0x2060 ... 0x2063:  // WORD JOINER..INVISIBLE SEPARATOR
        case 0x2064 ... 0x2069:
        case 0x206A ... 0x206F:  // INHIBIT SWAPPING..NOMINAL DIGIT SHAPES
        case 0xD800 ... 0xDFFF:
        case 0xFE00 ... 0xFE0F:  // VARIATION SELECTOR-1..VARIATION SELECTOR-16
        case 0xFEFF:             // ZERO WIDTH NO-BREAK SPACE
        case 0xFFF0 ... 0xFFF8:
        case 0xFFF9 ... 0xFFFB:  // INTERLINEAR ANNOTATION
#if WLITE_XBMP_CHAR
        case 0x1D173 ... 0x1D17A: // MUSICAL SYMBOL
        case 0xE0000:
        case 0xE0001:             // LANGUAGE TAG
        case 0xE0002 ... 0xE001F:
        case 0xE0020 ... 0xE007F: // TAG SPACE..CANCEL TAG
        case 0xE0080 ... 0xE0FFF:
#endif
            return !0;
        }
        return 0;
    case wlite_han_:
        switch (c) {
        case 0x2E80 ... 0x2E99:   // CJK RADICAL REPEAT..CJK RADICAL RAP
        case 0x2E9B ... 0x2EF3:   // CJK RADICAL CHOKE..CJK RADICAL CSIMP TURTLE
        case 0x2F00 ... 0x2FD5:   // KANGXI RADICAL ONE..KANGXI RADICAL FLUTE
        case 0x3005:              // IDEOGRAPHIC ITERATION MARK
        case 0x3007:              // IDEOGRAPHIC NUMBER ZERO
        case 0x3021 ... 0x3029:   // HANGZHOU NUMERAL 1..HANGZHOU NUMERAL 9
        case 0x3038 ... 0x303A:   // HANGZHOU NUMERAL 10..HANGZHOU NUMERAL 30
        case 0x303B:              // VERTICAL IDEOGRAPHIC ITERATION MARK
        case 0x3400 ... 0x4DB5:   // CJK UNIFIED IDEO..CJK UNIFIED IDEO
        case 0x4E00 ... 0x9FA5:   // CJK UNIFIED IDEO..CJK UNIFIED IDEO
        case 0xF900 ... 0xFA2D:   // CJK COMPAT IDEO..CJK COMPAT IDEO
        case 0xFA30 ... 0xFA6A:   // CJK COMPAT IDEO..CJK COMPAT IDEO
#if WLITE_XBMP_CHAR
        case 0x20000 ... 0x2A6D6: // CJK UNIFIED IDEO..CJK UNIFIED IDEO
        case 0x2F800 ... 0x2FA1D: // CJK COMPAT IDEO..CJK COMPAT IDEO
#endif
            return !0;
        default: return 0;
        }
    case wlite_hangul_:
        switch (c) {
        case 0x1100 ... 0x1159: // CHOSEONG KIYEOK..CHOSEONG YEORINHIEUH
        case 0x115F ... 0x11A2: // CHOSEONG FILLER..JUNGSEONG SSANGARAEA
        case 0x11A8 ... 0x11F9: // JONGSEONG KIYEOK..JONGSEONG YEORINHIEUH
        case 0x3131 ... 0x318E: // LETTER KIYEOK..LETTER ARAEAE
        case 0xAC00 ... 0xD7A3: // SYLLABLE GA..SYLLABLE HIH
        case 0xFFA0 ... 0xFFBE: // HALFWIDTH FILLER..HALFWIDTH LETTER HIEUH
        case 0xFFC2 ... 0xFFC7: // HALFWIDTH LETTER A..HALFWIDTH LETTER E
        case 0xFFCA ... 0xFFCF: // HALFWIDTH LETTER YEO..HALFWIDTH LETTER OE
        case 0xFFD2 ... 0xFFD7: // HALFWIDTH LETTER YO..HALFWIDTH LETTER YU
        case 0xFFDA ... 0xFFDC: // HALFWIDTH LETTER EU..HALFWIDTH LETTER I
            return !0;
        default: return 0;
        }
    case wlite_hira_:
        switch (c) {
        case 0x3041 ... 0x3096: // SMALL A..SMALL KE
        case 0x309D ... 0x309E: // ITERATION MARK..VOICED ITERATION MARK
        case 0x309F:            // DIGRAPH YORI
            return !0;
        default: return 0;
        }
    case wlite_kana_:
        return wlite_iswctype(c, wlite_hira_) || wlite_iswctype(c, wlite_kata_);
    case wlite_kata_:
        switch (c) {
        case 0x30A1 ... 0x30FA: // SMALL A..VO
        case 0x30FD ... 0x30FE: // ITERATION MARK..VOICED ITERATION MARK
        case 0x30FF:            // DIGRAPH KOTO
        case 0x31F0 ... 0x31FF: // SMALL KU..SMALL RO
        case 0xFF66 ... 0xFF6F: // HALFWIDTH WO..HALFWIDTH SMALL TU
        case 0xFF71 ... 0xFF9D: // HALFWIDTH A..HALFWIDTH N
            return !0;
        default: return 0;
        }
#endif
    }
    return 0;
}

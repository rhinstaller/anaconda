/*
 * $Id$
 *
 * Copyright (C) 2002  Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Original Author: Adrian Havill <havill@redhat.com>
 *
 * Contributors:
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>

#include "to_c.h"

void
set_class(unsigned long c, const char *class,
          wlite_bitarray_t_ *ambi, wlite_bitarray_t_ *wide) {
    if      (strncmp(class, "Na", 2) == 0) {
        set_bit(c, ambi, 0);
        set_bit(c, wide, 0);
    }
    else if (strncmp(class, "N ", 2) == 0) {
        set_bit(c, ambi, 0);
        set_bit(c, wide, 0);
    }
    else if (strncmp(class, "W ", 1) == 0) {
        set_bit(c, ambi, 0);
        set_bit(c, wide, 1);
    }
    else if (strncmp(class, "H ", 1) == 0) {
        set_bit(c, ambi, 0);
        set_bit(c, wide, 0);
    }
    else if (strncmp(class, "F ", 1) == 0) {
        set_bit(c, ambi, 0);
        set_bit(c, wide, 1);
    }
    else if (strncmp(class, "A ", 1) == 0) {
        set_bit(c, ambi, 1);
        set_bit(c, wide, WLITE_IS_CJK_(LC_CTYPE));
    }
    else fprintf(stderr, "unknown class: %s", class);
}

int main(int argc, char **argv) {
    wlite_bitarray_t_
    wlite_wide[(WLITE_WCHAR_MAX+1) / WLITE_BITARRAY_N_] = { 0 };

    wlite_bitarray_t_
    wlite_ambi[(WLITE_WCHAR_MAX+1) / WLITE_BITARRAY_N_] = { 0 };

    while (!feof(stdin)) {
        unsigned long c, lo = 0xFFFF, hi = 0xFFFF;
        char s[132] = { 0 }, class[132], *comment;

        if (fgets(s, sizeof(s), stdin) == NULL) {
            if (ferror(stdin))
                perror(NULL);
            break;
        }
        comment = strchr(s, '#');
        if (comment != NULL)
            strcpy(comment, "\n");
        if (strstr(s, "..") == NULL) {
            if (sscanf(s, " %lX ; %s", &c, class) != 2) {
                fprintf(stderr, "can't scan 2: %s", s);
                continue;
            }
            hi = lo = c;
        }
        else {
            if (sscanf(s, " %lX .. %lX ; %s", &lo, &hi, class) != 3) {
                fprintf(stderr, "can't scan 3: %s", s);
                continue;
            }
        }
        for (c = lo; c <= hi; c++)
            set_class(c, class, wlite_ambi, wlite_wide);
    }

    fprintf(stdout, "#include \"%s\"\n", "wlite_config.h");

    print_bits(stdout, wlite_wide, WLITE_ID2STR_(wlite_wide));

#if WLITE_AMBI_LOCALE
    print_bits(stdout, wlite_ambi, WLITE_ID2STR_(wlite_ambi));
#endif

    return 0;
}

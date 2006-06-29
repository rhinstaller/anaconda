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

#include <locale.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "to_c.h"

int main(int argc, char **argv) {
    wlite_map_t_ *wlite_case = NULL;
    size_t case_n = 0;

    if (setlocale(LC_CTYPE, "") == NULL) {
        fputs("couldn't set CTYPE locale\n", stderr);
    }
    while (!feof(stdin)) {
        unsigned long from = 0xFFFF, to = 0xFFFF;
        char s[132] = { 0 }, class = '\0', *comment;

        if (fgets(s, sizeof(s), stdin) == NULL) {
            if (ferror(stdin))
                perror(NULL);
            break;
        }
        comment = strchr(s, '#');
        if (comment != NULL) {
            strcpy(comment, "\n");
        }
        if (sscanf(s, " %lX ; %c ; %lX ;", &from, &class, &to) != 3) {
            fprintf(stderr, "can't scan 3: %s", s);
            continue;
        }
        if (class != 'C' && class != 'S') {
            fprintf(stderr, "skipping '%c' map for: %s", class, s);
            continue;
        }
        add_map((wchar_t) from, (wchar_t) to, &wlite_case, &case_n);
    }

    fprintf(stdout, "#include \"%s\"\n", "wlite_config.h");

    print_maps(stdout, wlite_case, WLITE_ID2STR_(wlite_case), case_n);

    return 0;
}

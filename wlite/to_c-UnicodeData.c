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

#include <errno.h>
#include <locale.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "to_c.h"

char *get_field(const char *line, unsigned n) {
    const char *semi;
    char *field = NULL;
    size_t length;
    unsigned i;

    for (i = 0, semi = line; i < n; i++, semi++) {
        if ((semi = strchr(semi, ';')) == NULL) {
            fprintf(stderr, "can't get field #%u from '%s'\n", n, line);
            break;
        }
    }
    length = strcspn(semi, ";");
    if ((field = malloc(length + 1)) == NULL) {
        perror(NULL);
        exit(EXIT_FAILURE);
    }
    strncpy(field, semi, length);
    field[length] = '\0';
    return field;
}

int main(int argc, char **argv) {
    wlite_wc_t_ *wlite_punct = NULL; size_t punctn = 0;
    wlite_map_t_ *wlite_fixw = NULL; size_t fixw_n = 0;

    if (setlocale(LC_CTYPE, "") == NULL) {
        fputs("couldn't set locale for LC_CTYPE\n", stderr);
    }
    while (!feof(stdin)) {
        unsigned long codepoint, decomp;
        char line[512] = { 0 }, *comment, *field;

        if (fgets(line, sizeof(line), stdin) == NULL) {
            if (ferror(stdin)) {
                perror(NULL);
                exit(EXIT_FAILURE);
            }
            break;
        }
        if ((comment = strchr(line, '#')) != NULL) {
            strcpy(comment, "\n");
        }

        /* get character in question */

        if (sscanf(line, " %lX ;", &codepoint) != 1) continue;

        /* get character category */

        if ((field = get_field(line, 2)) != NULL) {
            if (field[0] == 'P') {
                fprintf(stderr, "adding punctuation U+%04lX\n", codepoint);
                add_wc((wchar_t) codepoint, &wlite_punct, &punctn);
            }
            free(field);
        }

        /* get character decomposition */

        if ((field = get_field(line, 5)) != NULL) {
            if (strstr(field, "<narrow>") != NULL) {
                if (sscanf(field, "<narrow> %lX ;", &decomp) != 1) {
                    fprintf(stderr, "can't scan field: %s", field);
                }
                else {
                    fprintf(stderr, "adding halfwidth U+%04lX -> U+%04lX\n",
                            codepoint, decomp);
                    add_map(codepoint, decomp, &wlite_fixw, &fixw_n);
                }
                   
            }
            free(field);
        }

        if ((field = get_field(line, 5)) != NULL) {
            if (strstr(field, "<wide>") != NULL) {
                if (sscanf(field, "<wide> %lX ;", &decomp) != 1) {
                    fprintf(stderr, "can't scan field: %s", field);
                }
                else {
                    fprintf(stderr, "adding fullwidth U+%04lX -> U+%04lX\n",
                            codepoint, decomp);
                    add_map(codepoint, decomp, &wlite_fixw, &fixw_n);
                }
                   
            }
            free(field);
        }

    }

    fprintf(stdout, "#include \"%s\"\n", "wlite_config.h");

    print_wcs(stdout, wlite_punct, WLITE_ID2STR_(wlite_punct), punctn);
    print_maps(stdout, wlite_fixw, WLITE_ID2STR_(wlite_fixw), fixw_n);

    return 0;
}

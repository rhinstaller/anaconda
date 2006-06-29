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

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

#include "to_c.h"

const char *const arrayfmt = "const %s %s[%zu] = {";
const char *const arraynfmt = "const size_t %s_n = %zu;\n";

void set_bit(wchar_t c, wlite_bitarray_t_ *bits, int bit) {
    size_t i;
    int j;

    if (c <= WLITE_WCHAR_MAX) {
        i = c / WLITE_BITARRAY_N_;
        j = c % WLITE_BITARRAY_N_;
        if (bit) {
            bits[i] |= ((wlite_bitarray_t_) 1 << j);
        }
        else bits[i] &= ~((wlite_bitarray_t_) 1 << j);
    }
}

void add_map(wchar_t c, wchar_t to, wlite_map_t_ *map[], size_t *n) {
    if (c > WLITE_WCHAR_MAX) {
        fprintf(stderr, "ignoring high char: %lX\n", c);
        return;
    }
    if (to > WLITE_WCHAR_MAX) {
        fprintf(stderr, "ignoring high char: %lX\n", to);
        return;
    }
    *map = realloc(*map, (*n + 1) * sizeof(wlite_map_t_));
    if (*map == NULL) {
        perror(NULL);
        exit(EXIT_FAILURE);
    }
    (*map)[*n].from = c;
    (*map)[*n].to = to;
    ++*n;
}

void add_wc(wchar_t c, wlite_wc_t_ *wide[], size_t *n) {
    if (c > WLITE_WCHAR_MAX) {
        fprintf(stderr, "ignoring high char: %lX\n", (unsigned long) c);
        return;
    }
    *wide = realloc(*wide, (*n + 1) * sizeof(wlite_wc_t_));
    if (*wide == NULL) {
        perror(NULL);
        exit(EXIT_FAILURE);
    }
    (*wide)[*n] = (wlite_wc_t_) c;
    *n += 1;
}

void print_bits(FILE *stream, const wlite_bitarray_t_ *bits, const char *name) {
    size_t x;
    const size_t max = (WLITE_WCHAR_MAX + 1) / WLITE_BITARRAY_N_;
    const size_t hex_per_line = 6;

    fprintf(stream, arrayfmt, WLITE_ID2STR_(wlite_bitarray_t_), name, max);
    fputc('\n', stream);
    for (x = 0; x < max; x++) {
        if (x % hex_per_line == 0)
            fputs("  ", stream);
        fprintf(stream, "%0#10lx", (unsigned long) bits[x]);
        if (x + 1 < max)
            fputc(',', stream);
        if (((x + 1) % hex_per_line) == 0) {
            unsigned long bit_1 = (x - hex_per_line + 1) * WLITE_BITARRAY_N_;
#if WLITE_XBMP_CHAR
            const char *const fmt = " //U-%06lX\n";
#else
            const char *const fmt = " //U+%04lX\n";
#endif
            fprintf(stream, fmt, bit_1);
        }
    }
    if (x % hex_per_line != 0)
        fputc('\n', stream);
    fputs("};\n\n", stream);
}

void print_maps(FILE *stream, wlite_map_t_ map[], const char *name, size_t n) {
    size_t i;
#if WLITE_XBMP_CHAR
    const char *const fmt = "{ %0#8lx, %0#8lx }";
    const char *const cmt = "\\U%08lX";
#else
    const char *const fmt = "{ %0#6lx, %0#6lx }";
    const char *const cmt = "  \\u%04lX  ";
#endif

    qsort(map, n, sizeof(wlite_map_t_), wlite_map_t_cmp_);
    fprintf(stream, arraynfmt, name, n);
    fprintf(stream, arrayfmt, WLITE_ID2STR_(wlite_map_t_), name, n);
    for (i = 0; i < n; i++) {
        unsigned long from = (unsigned long) map[i].from;
        unsigned long to = (unsigned long) map[i].to;

        fputs("\n    ", stream);
        fprintf(stream, fmt, from, to);
        fputs(i + 1 < n ? "," : " ", stream);
        if (fprintf(stream, " // (%10lc", (wint_t) from) < 0) {
            if (errno == EILSEQ) {
                fprintf(stream, cmt, from);
                errno = 0;
            }
            else {
                perror(NULL);
                exit(EXIT_FAILURE);
            }
        }
        if (fprintf(stream, "->%-10lc)", (wint_t) to) < 0) {
            if (errno == EILSEQ) {
                fprintf(stream, cmt, to);
                fputc(')', stream);
                errno = 0;
            }
            else {
                perror(NULL);
                exit(EXIT_FAILURE);
            }
        }
    }
    fputs("\n};\n\n", stream);
}

void print_wcs(FILE *stream, wlite_wc_t_ *wide, const char *name, size_t n) {
    size_t i;
    const size_t hex_per_line = 8;
    const char* const type = WLITE_ID2STR_(wlite_wc_t_);

    qsort(wide, n, sizeof(wlite_wc_t_), wlite_wc_t_cmp_);
    fprintf(stream, arraynfmt, name, n);
    fprintf(stream, arrayfmt, type, name, n);
    for (i = 0; i < n; i++) {
        unsigned long wc = (unsigned long) wide[i];

        if (i % hex_per_line == 0)
            fputs("\n    ", stream);
#if WLITE_XBMP_CHAR
            fprintf(stream, "%0#8lx", wc);
#else
            fprintf(stream, "%0#6lx", wc);
#endif
        if (i + 1 < n)
            fputc(',', stream);
    }
    if (i % hex_per_line != 0)
        fputc('\n', stream);
    fputs("};\n\n", stream);
}

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

#include <stdio.h>

#define WLITE_REDEF_STDC 0

#include "wlite_config.h"
#include "wlite_wchar.h"
#include "wlite_wctype.h"

void set_bit(wchar_t c, wlite_bitarray_t_ bits[], int bit);
void add_map(wchar_t c, wchar_t to, wlite_map_t_ *map[], size_t *);
void add_wc(wchar_t c, wlite_wc_t_ *wide[], size_t *);

void print_bits(FILE *, const wlite_bitarray_t_ bits[], const char *name);
void print_maps(FILE *, wlite_map_t_ map[], const char *name, size_t);
void print_wcs(FILE *, wlite_wc_t_ wide[], const char *name, size_t);

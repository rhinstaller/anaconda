/*
 * str.c - String helper functions that don't need string.h or ctype.h
 *
 * Copyright 2006 Red Hat, Inc.
 *
 * David Cantrell <dcantrell@redhat.com>
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <stdio.h>
#include <stdlib.h>

#include "str.h"

/**
 * Convert given string to uppercase. Modifies the argument in the caller's
 * stack. If you must ask simply "why?" for this function, it's so we don't
 * need toupper() and the same for loop all over the place.
 *
 * LIMITATIONS: Only deals with ASCII character set.
 *
 * @param str String to convert to uppercase.
 * @return Pointer to str.
 */
char *str2upper(char *str) {
    char *tmp;

    if (str == NULL)
        return NULL;

    /* man ascii(7) */
    tmp = str;
    while (*tmp != '\0') {
        if (*tmp >= 'a' && *tmp <= 'z')
            *tmp -= 32;

        tmp++;
    }

    return str;
}

/* vim:set shiftwidth=4 softtabstop=4: */

/* telnet.c -- basic telnet protocol handling for ttywatch
 *
 * Copyright © 2001 Michael K. Johnson <johnsonm@redhat.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 */

/* Shamelessly stolen from ttywatch -- oot */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "telnet.h"
#include "log.h"

#define IAC "\xff"
#define DONT "\xfe"
#define WONT "\xfc"
#define WILL "\xfb"
#define DO "\xfd"
#define SB "\xfa"
#define SE "\xf0"
#define ECHO "\x01"
#define SUPPRESS_GO_AHEAD "\x03"
#define LINEMODE "\x22"
#define NEWENVIRON "\x27"
#define MODE "\x01"

/* Make a request.  Not intended to be RFC-compatible, just enough
 * to convince telnet clients to do what we want...  To do this
 * right, we would have to honestly negotiate, not speak blind.
 *
 * For now, assume all responses will be favorable and stripped
 * out in telnet_process_input()...  Sending it all in a single
 * write makes it more efficient because it will all go out in a
 * single packet, and the responses are more likely to all come
 * back in a single packet (and thus, practically, a single read)
 * too.
 */
void
telnet_negotiate(int socket) {
    char request[]=
      IAC DONT ECHO
      IAC WILL ECHO
      IAC WILL SUPPRESS_GO_AHEAD
      IAC DO SUPPRESS_GO_AHEAD
      IAC DONT NEWENVIRON
      IAC WONT NEWENVIRON
      IAC DO LINEMODE
      IAC SB LINEMODE MODE "0" IAC SE
      ;
    write(socket, request, sizeof(request)-1);
}

int
telnet_process_input(telnet_state * ts, char *data, int len) {
    char *s, *d; /* source, destination */

#   define DEBUG_TELNET 0
#   if DEBUG_TELNET
    printf("\nprinting packet:");
    for (s=data; s<data+len; s++) {
	if (!((s-data)%10))
	    printf("\n %03d: ", s-data);
	printf("%02x ", *s & 0x000000FF);
    }
    printf("\n");
#   endif /* DEBUG_TELNET */

    for (s=data, d=data; s<data+len; s++) {
	switch (*ts) {
	case TS_DATA:
	    if (*s == '\xff') { /* IAC */
		*ts = TS_IAC;
		continue;
	    }
#if	    DEBUG_TELNET
	    printf("copying data element '%c'\n", *s);
#endif	    /* DEBUG_TELNET */
	    if (s>d) {
		*(d++) = *s;
	    } else {
		d++;
	    }
	    break;

	case TS_IAC:
	    if (*s == '\xfa') { /* SB */
		*ts = TS_SB;
		continue;
	    }
	    /* if not SB, skip IAC verb object */
#	    if DEBUG_TELNET
	    printf("skipping verb/object (offset %d)...\n", s-data-1);
#	    endif /* DEBUG_TELNET */
	    s += 1;
	    *ts = TS_DATA;
	    break;

	case TS_SB:
#	    if DEBUG_TELNET
	    printf("skipping SB (offset %d)...\n", s-data-1);
#	    endif /* DEBUG_TELNET */
	    while (s < (data+(len-1))) {
		if (*s == '\xff') {
		    break; /* fall through to TS_SB_IAC setting below */
		} else {
		    s++;
		}
	    }
	    if (*s == '\xff') {
		*ts = TS_SB_IAC;
	    }
	    break;

	case TS_SB_IAC:
	    if (*s == '\xf0') { /* SE */
#		if DEBUG_TELNET
		printf("SE ends SB (offset %d)...\n", s-data-1);
#		endif /* DEBUG_TELNET */
		*ts = TS_DATA;
	    } else {
#		if DEBUG_TELNET
		printf("IAC without SE in SB\n");
#		endif /* DEBUG_TELNET */
		*ts = TS_SB;
	    }
	    break;

	default:
	    logMessage("unknown telnet state %d for data element %c", *ts, *s);
	    *ts = TS_DATA;
	    break;
	}
    }

    /* calculate new length after copying data around */
    len = d - data;
#if DEBUG_TELNET
    printf("returning len: %d of packet:", len);
    for (s=data; s<data+len; s++) {
	if (!((s-data)%10))
	    printf("\n %03d: ", s-data);
	printf("%02x ", *s & 0x000000FF);
    }
    printf("\n");
#endif /* DEBUG_TELNET */
    return len;
}

/* The telnet protocol requires CR/NL instead of just NL
 * We normally deal with Unix, which just uses NL, so we need to translate.
 *
 * It would be easy to go through line-by-line and write each line, but
 * that would create more packet overhead by sending out one packet
 * per line, and over things like slow PPP connections, that is painful.
 * Therefore, instead, we create a modified copy of the data and write
 * the whole modified copy at once.
 */
void
telnet_send_output(int sock, char *data, int len) {
    char *s, *d; /* source, destination */
    char *buf;

    buf = alloca((len*2)+1);  /* max necessary size */

    /* just may need to add CR before NL (but do not double existing CRs) */
    for (s=data, d=buf; d-buf<len; s++, d++) {
	if ((*s == '\n') && (s == data || (*(s-1) != '\r'))) {
	    /* NL without preceding CR */
	    *(d++) = '\r';
	    len++;
	}
	*d = *s;
    }

    /* now send it... */
    write(sock, buf, len);
}

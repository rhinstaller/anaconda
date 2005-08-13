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

#include <ctype.h>
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
#define TERMINAL_TYPE "\x18"
#define NAWS "\x1f"
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
telnet_negotiate(int socket, char ** term_type_ptr, int * heightPtr,
		 int * widthPtr) {
    char ch;
    int done = 0;
    char * termType = NULL;
    int termLength = 0, termAlloced = 0;
    enum { ST_NONE, ST_TERMTYPE, ST_WINDOWSIZE } state;
    char sizeBuf[4];
    int height = -1, width = -1;
    char * sizePtr = sizeBuf;
    char request[]=
      IAC DONT ECHO
      IAC WILL ECHO
      IAC WILL NAWS
      IAC WILL SUPPRESS_GO_AHEAD
      IAC DO SUPPRESS_GO_AHEAD
      IAC DONT NEWENVIRON
      IAC WONT NEWENVIRON
      IAC WONT LINEMODE
      IAC DO NAWS
      IAC SB TERMINAL_TYPE "\x01" IAC SE
      ;
    int ret;

    ret = write(socket, request, sizeof(request)-1);

    /* Read from the terminal until we get the terminal type. This will
       do bad things if the client doesn't send the terminal type, but
       those clients have existed for aeons (right?) */

    do {
	ret = read(socket, &ch, 1);
	if (ch != '\xff') {
	    abort();
	}

	ret = read(socket, &ch, 1);	    /* command */

	if (ch != '\xfa') {
	    ret = read(socket, &ch, 1);   /* verb */
	    continue;
	}

	ret = read(socket, &ch, 1);   /* suboption */
	if (ch == '\x18') {
	    state = ST_TERMTYPE;
	    ret = read(socket, &ch, 1);	    /* should be 0x0! */
	    done = 1;
	} else if (ch == '\x1f') {
	    state = ST_WINDOWSIZE;
	} else {
	    state = ST_NONE;;
	}

	ret = read(socket, &ch, 1);   /* data */
	while (ch != '\xff') {
	    if (state == ST_TERMTYPE) {
		if (termAlloced == termLength) {
		    termAlloced += 10;
		    termType = realloc(termType, termAlloced + 1);
		}

		termType[termLength++] = tolower(ch);
	    } else if (state == ST_WINDOWSIZE) {
		if ((sizePtr - sizeBuf) < (int)sizeof(sizeBuf))
		    *sizePtr++ = ch;
	    }

	    ret = read(socket, &ch, 1);   /* data */
	}

	ret = read(socket, &ch, 1);   /* should be a SE */

    } while (!done);

    termType[termLength] = '\0';

    if (sizePtr - sizeBuf == sizeof(sizeBuf)) {
	width = (sizeBuf[0] << 8) + sizeBuf[1];
	height = (sizeBuf[2] << 8) + sizeBuf[3];
    }

    if (heightPtr) *heightPtr = height;
    if (widthPtr) *widthPtr = width;

    if (term_type_ptr) *term_type_ptr = termType;
}

int
telnet_process_input(telnet_state * ts, char *data, int len) {
    char *s, *d; /* source, destination */

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
		printf("IAC without SE in SB (offset %d)\n", s-data-1);
#		endif /* DEBUG_TELNET */
		*ts = TS_SB;
	    }
	    break;

	default:
	    logMessage(WARNING, "unknown telnet state %d for data element %c",
                       *ts, *s);
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
    int ret;

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
    ret = write(sock, buf, len);
}

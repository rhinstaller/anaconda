/* telnet.h -- basic telnet protocol handling for ttywatch
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


#ifndef __TELNET_H__
#define __TELNET_H__

typedef enum {
	TS_DATA = 0,
	TS_IAC,
	TS_SB,
	TS_SB_IAC,
} telnet_state;

void
telnet_negotiate(int socket, char ** term_type_ptr, int * heightPtr,
		 int * widthPtr);
int
telnet_process_input(telnet_state * ts, char *data, int len);
void
telnet_send_output(int sock, char *data, int len);

#endif /* __TELNET_H__ */

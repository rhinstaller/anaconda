/*
 * telnetd.c - glue to tie telnet.c from ttywatch to the loader
 *
 * Erik Troan <ewt@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <newt.h>
#include <pty.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/poll.h>
#include <sys/signal.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#include "lang.h"
#include "loader.h"
#include "log.h"
#include "modules.h"
#include "net.h"
#include "telnet.h"
#include "windows.h"

#include "../isys/probe.h"

#ifndef IPPORT_TELNET
#define IPPORT_TELNET 23
#endif

/* Forks, keeping the loader as our child (so we know when it dies). */
int beTelnet(int flags) {
    int sock;
    int conn;
    int addrLength;
    pid_t child;
    int i;
    int masterFd;
    struct sockaddr_in address;
    char buf[4096];
    struct pollfd fds[3];
    telnet_state ts = TS_DATA;
    char * termType;
    int height, width;
    struct winsize ws;

    if ((sock = socket(PF_INET, SOCK_STREAM, 0)) < 0) {
	logMessage("socket: %s", strerror(errno));
	return -1;
    }

    address.sin_family = AF_INET;
    address.sin_port = htons(IPPORT_TELNET);
    memset(&address.sin_addr, 0, sizeof(address.sin_addr));
    addrLength = sizeof(address);

    /* Let the kernel reuse the socket address. This lets us run
       twice in a row, without waiting for the (ip, port) tuple
       to time out. Makes testing much easier*/
    conn = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &conn, sizeof(conn));

    bind(sock, (struct sockaddr *) &address, sizeof(address));
    listen(sock, 5);

    winStatus(45, 3, _("Telnet"), _("Waiting for telnet connection..."));

    if ((conn = accept(sock, (struct sockaddr *) &address, 
                          &addrLength)) < 0) {
	newtWinMessage(_("Error"), _("OK"), "accept failed: %s", 
		       strerror(errno));
	close(sock);
	return -1;
    }

    stopNewt();

    close(sock);

    telnet_negotiate(conn, &termType, &height, &width);

#ifdef DEBUG
    printf("got term type %s\n", termType);
#endif

    masterFd = open("/dev/ptyp0", O_RDWR);
    if (masterFd < 0) {
	logMessage("cannot open /dev/ttyp0");
	close(conn);
	return -1;
    }

    if (height != -1 && width != -1) {
#ifdef DEBUF
	printf("setting window size to %d x %d\n", width, height);
#endif
	ws.ws_row = height;
	ws.ws_col = width;
	ioctl(masterFd, TIOCSWINSZ, &ws);
    }


    child = fork();

    if (child) {
#ifndef DEBUG
	startNewt(flags);
	winStatus(45, 3, _("Telnet"), _("Running anaconda via telnet..."));
#endif

	fds[0].events = POLLIN;
	fds[0].fd = masterFd;

	fds[1].events = POLLIN;
	fds[1].fd = conn;

	while ((i = poll(fds, 2, -1)) > 0) {
	    if (fds[0].revents) {
		i = read(masterFd, buf, sizeof(buf));

#ifdef DEBUG
		{
		    int j;
		    int row;

		    for (row = 0; row < (i / 12) + 1; row++) {
			printf("wrote:");
			for (j = (row * 12); j < i && j < ((row + 1) * 12); j++)
			    printf(" 0x%2x", (unsigned char) buf[j]);
			printf("\n");
			printf("wrote:");
			for (j = (row * 12); j < i && j < ((row + 1) * 12); j++)
			{
			    if (isprint(buf[j]))
				printf("   %c ", buf[j]);
			    else
				printf("     ");
			}
			printf("\n");
		    }
		}
#endif
		/* child died */
		if (i < 0)
		    break;

		telnet_send_output(conn, buf, i);
	    }

	    if (fds[1].revents) {
		i = read(conn, buf, sizeof(buf));

		/* connection went away */
		if (!i)
		    break;

		i = telnet_process_input(&ts, buf, i);
		write(masterFd, buf, i);

#ifdef DEBUG
		{
		    int j;

		    printf("got:");
		    for (j = 0; j < i; j++)
			printf(" 0x%x", (unsigned char) buf[j]);
		    printf("\n");
		}
#endif

	    }
	}


	if (i < 0) {
	    logMessage("poll: %s", strerror(errno));
	} 

#ifndef DEBUG
	stopNewt();
#endif

	kill(child, SIGTERM);
	close(conn);

	exit(0);
    }

    close(masterFd);
    setsid();
    close(0);
    close(1);
    close(2);

    open("/dev/ttyp0", O_RDWR);
    dup(0);
    dup(0);

    /* brand new tty! */
    setenv("TERM", termType, 1);

    startNewt(flags);

    return 0;
}

void startTelnetd(struct knownDevices * kd, struct loaderData_s * loaderData,
                  moduleInfoSet modInfo, moduleList modLoaded, 
                  moduleDeps modDeps, int flags) {
    if (kickstartNetworkUp(kd, loaderData, flags)) {
        logMessage("unable to bring up network");
        return;
    }

    logMessage("going to beTelnet");
    if (!beTelnet(flags))
        flags |= LOADER_FLAGS_TEXT | LOADER_FLAGS_NOSHELL;

    return;
}

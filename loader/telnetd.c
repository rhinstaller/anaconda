/* Glue to tie telnet.c from ttywatch to the loader */

#include <arpa/inet.h>
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
#include "telnet.h"
#include "windows.h"

#ifndef IPPORT_TELNET
#define IPPORT_TELNET 23
#endif

#define DEBUG

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

    telnet_negotiate(conn, &termType);

    printf("got term type %s\n", termType);
    printf("term is currently %s\n", getenv("TERM"));

    sleep(3);

    masterFd = open("/dev/ptyp0", O_RDWR);
    if (masterFd < 0) {
	logMessage("cannot open /dev/ttyp0");
	close(conn);
	return -1;
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

#ifdef DEBUG
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

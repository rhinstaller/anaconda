/* Glue to tie telnet.c from ttywatch to the loader */

#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <pty.h>
#include <string.h>
#include <sys/poll.h>
#include <sys/signal.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <termios.h>
#include <unistd.h>

#include "log.h"
#include "telnet.h"

/* Forks, keeping the loader as our child (so we know when it dies). */
int beTelnet(void) {
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
    struct termios orig, new;

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

    printf("Waiting for telnet connection on port 23...");

    if ((conn = accept(sock, (struct sockaddr *) &address, 
                          &addrLength)) < 0) {
	logMessage("accept: %s", strerror(errno));
	exit(0);
	return -1;
    }

    printf(" got a connection.\n");

    close(sock);

    telnet_negotiate(conn);
    child = forkpty(&masterFd, NULL, NULL, NULL);

    if (child < 0) {
	logMessage("forkpty: %s", strerror(errno));
	close(conn);
	return -1;
    } else if (child) {
	fds[0].events = POLLIN;
	fds[0].fd = masterFd;

	fds[1].events = POLLIN;
	fds[1].fd = conn;

	fds[2].events = POLLIN;
	fds[2].fd = STDIN_FILENO;

	tcgetattr(STDIN_FILENO, &orig);
	tcgetattr(STDIN_FILENO, &new);
	new.c_lflag &= ~(ICANON | ECHO | ECHOCTL | ECHONL);
	new.c_oflag &= ~ONLCR;
	new.c_iflag &= ~ICRNL;
	new.c_cc[VSUSP] = 0;
	tcsetattr(STDIN_FILENO, 0, &new);

	while ((i = poll(fds, 3, -1)) > 0) {
	    if (fds[0].revents) {
		i = read(masterFd, buf, sizeof(buf));

		/* child died */
		if (i < 0)
		    break;

		telnet_send_output(conn, buf, i);
		write(STDOUT_FILENO, buf, i);
	    }

	    if (fds[1].revents) {
		i = read(conn, buf, sizeof(buf));

		/* connection went away */
		if (!i)
		    break;

		i = telnet_process_input(&ts, buf, i);
		write(masterFd, buf, i);
	    }

	    if (fds[2].revents) {
		i = read(STDIN_FILENO, buf, sizeof(buf));
		write(masterFd, buf, i);
	    }
	}

	printf("out of poll %d\n", i);

	if (i < 0) {
	    logMessage("poll: %s", strerror(errno));
	} 

	kill(child, SIGTERM);
	close(conn);
	tcsetattr(STDIN_FILENO, 0, &orig);

	exit(0);
    }

    return 0;
}

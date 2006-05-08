/*
 * ftp.c - ftp code
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */



#define HAVE_ALLOCA_H 1
#define HAVE_NETINET_IN_SYSTM_H 1
#define HAVE_SYS_SOCKET_H 1
#define USE_ALT_DNS 1

#if HAVE_ALLOCA_H
# include <alloca.h>
#endif

#if HAVE_SYS_SOCKET_H
# include <sys/socket.h>
#endif

#if HAVE_NETINET_IN_SYSTM_H
# include <sys/types.h>
# include <netinet/in_systm.h>
#endif

#if ! HAVE_HERRNO
extern int h_errno;
#endif

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <pwd.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

#include <netinet/in.h>
#include <netinet/ip.h>
#include <arpa/inet.h>

#define TIMEOUT_SECS 60
#define BUFFER_SIZE 4096

#ifndef IPPORT_FTP
# define IPPORT_FTP 21
#endif

#if defined(USE_ALT_DNS) && USE_ALT_DNS 
#include "../isys/dns.h"
#endif

#include "ftp.h"

static int ftpCheckResponse(int sock, char ** str);
static int ftpCommand(int sock, char * command, ...);
static int getHostAddress(const char * host, struct in_addr * address);

static int ftpCheckResponse(int sock, char ** str) {
    static char buf[BUFFER_SIZE + 1];
    int bufLength = 0; 
    fd_set emptySet, readSet;
    char * chptr, * start;
    struct timeval timeout;
    int bytesRead, rc = 0;
    int doesContinue = 1;
    char errorCode[4];
 
    errorCode[0] = '\0';
    
    do {
	FD_ZERO(&emptySet);
	FD_ZERO(&readSet);
	FD_SET(sock, &readSet);

	timeout.tv_sec = TIMEOUT_SECS;
	timeout.tv_usec = 0;
    
	rc = select(sock + 1, &readSet, &emptySet, &emptySet, &timeout);
	if (rc < 1) {
	    if (rc==0) 
		return FTPERR_BAD_SERVER_RESPONSE;
	    else
		rc = FTPERR_UNKNOWN;
	} else
	    rc = 0;

	bytesRead = read(sock, buf + bufLength, sizeof(buf) - bufLength - 1);

	bufLength += bytesRead;

	buf[bufLength] = '\0';

	/* divide the response into lines, checking each one to see if 
	   we are finished or need to continue */

	start = chptr = buf;

	do {
	    while (*chptr != '\n' && *chptr) chptr++;

	    if (*chptr == '\n') {
		*chptr = '\0';
		if (*(chptr - 1) == '\r') *(chptr - 1) = '\0';
		if (str) *str = start;

		if (errorCode[0]) {
		    if (!strncmp(start, errorCode, 3) && start[3] == ' ')
			doesContinue = 0;
		} else {
		    strncpy(errorCode, start, 3);
		    errorCode[3] = '\0';
		    if (start[3] != '-') {
			doesContinue = 0;
		    } 
		}

		start = chptr + 1;
		chptr++;
	    } else {
		chptr++;
	    }
	} while (*chptr);

	if (doesContinue && chptr > start) {
	    memcpy(buf, start, chptr - start - 1);
	    bufLength = chptr - start - 1;
	} else {
	    bufLength = 0;
	}
    } while (doesContinue && !rc);

    if (*errorCode == '4' || *errorCode == '5') {
	if (!strncmp(errorCode, "421", 3)) {
	    return FTPERR_TOO_MANY_CONNECTIONS;
	}
	else if (!strncmp(errorCode, "550", 3)) {
	    return FTPERR_FILE_NOT_FOUND;
	}

	return FTPERR_BAD_SERVER_RESPONSE;
    }

    if (rc) return rc;

    return 0;
}

int ftpCommand(int sock, char * command, ...) {
    va_list ap;
    int len;
    char * s;
    char * buf;
    int rc;

    va_start(ap, command);
    len = strlen(command) + 2;
    s = va_arg(ap, char *);
    while (s) {
	len += strlen(s) + 1;
	s = va_arg(ap, char *);
    }
    va_end(ap);

    buf = alloca(len + 1);

    va_start(ap, command);
    strcpy(buf, command);
    strcat(buf, " ");
    s = va_arg(ap, char *);
    while (s) {
	strcat(buf, s);
	strcat(buf, " ");
	s = va_arg(ap, char *);
    }
    va_end(ap);

    buf[len - 2] = '\r';
    buf[len - 1] = '\n';
    buf[len] = '\0';
     
    if (write(sock, buf, len) != len) {
        return FTPERR_SERVER_IO_ERROR;
    }

    if ((rc = ftpCheckResponse(sock, NULL)))
	return rc;

    return 0;
}


static int getHostAddress(const char * host, struct in_addr * address) {
    if (isdigit(host[0])) {
      if (!inet_pton(AF_INET, host, address)) {
	  return FTPERR_BAD_HOST_ADDR;
      }
    } else {
      if (mygethostbyname((char *) host, address)) {
	  errno = h_errno;
	  return FTPERR_BAD_HOSTNAME;
      }
    }
    
    return 0;
}

int ftpOpen(char * host, char * name, char * password, char * proxy,
	    int port) {
    static int sock;
    /*static char * lastHost = NULL;*/
    struct in_addr serverAddress;
    struct sockaddr_in destPort;
    struct passwd * pw;
    char * buf;
    int rc;

    if (port < 0) port = IPPORT_FTP;

    if (!name)
	name = "anonymous";

    if (!password) {
	password = "root@";
	if (getuid()) {
	    pw = getpwuid(getuid());
	    if (pw) {
		password = alloca(strlen(pw->pw_name) + 2);
		strcpy(password, pw->pw_name);
		strcat(password, "@");
	    }
	}
    }

    if (proxy) {
	buf = alloca(strlen(name) + strlen(host) + 5);
	sprintf(buf, "%s@%s", name, host);
	name = buf;
	host = proxy;
    }

    if ((rc = getHostAddress(host, &serverAddress))) return rc;

    sock = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (sock < 0) {
        return FTPERR_FAILED_CONNECT;
    }

    destPort.sin_family = AF_INET;
    destPort.sin_port = htons(port);
    destPort.sin_addr = serverAddress;

    if (connect(sock, (struct sockaddr *) &destPort, sizeof(destPort))) {
	close(sock);
        return FTPERR_FAILED_CONNECT;
    }

    /* ftpCheckResponse() assumes the socket is nonblocking */
    if (fcntl(sock, F_SETFL, O_NONBLOCK)) {
	close(sock);
        return FTPERR_FAILED_CONNECT;
    }

    if ((rc = ftpCheckResponse(sock, NULL))) {
        return rc;     
    }

    if ((rc = ftpCommand(sock, "USER", name, NULL))) {
	close(sock);
	return rc;
    }

    if ((rc = ftpCommand(sock, "PASS", password, NULL))) {
	close(sock);
	return rc;
    }

    if ((rc = ftpCommand(sock, "TYPE", "I", NULL))) {
	close(sock);
	return rc;
    }

    return sock;
}

int ftpGetFileDesc(int sock, char * remotename) {
    int dataSocket;
    struct sockaddr_in dataAddress;
    int i, j;
    char * passReply;
    char * chptr;
    char * retrCommand;
    int rc;

    if (write(sock, "PASV\r\n", 6) != 6) {
        return FTPERR_SERVER_IO_ERROR;
    }
    if ((rc = ftpCheckResponse(sock, &passReply)))
	return FTPERR_PASSIVE_ERROR;

    chptr = passReply;
    while (*chptr && *chptr != '(') chptr++;
    if (*chptr != '(') return FTPERR_PASSIVE_ERROR; 
    chptr++;
    passReply = chptr;
    while (*chptr && *chptr != ')') chptr++;
    if (*chptr != ')') return FTPERR_PASSIVE_ERROR;
    *chptr-- = '\0';

    while (*chptr && *chptr != ',') chptr--;
    if (*chptr != ',') return FTPERR_PASSIVE_ERROR;
    chptr--;
    while (*chptr && *chptr != ',') chptr--;
    if (*chptr != ',') return FTPERR_PASSIVE_ERROR;
    *chptr++ = '\0';
    
    /* now passReply points to the IP portion, and chptr points to the
       port number portion */

    dataAddress.sin_family = AF_INET;
    if (sscanf(chptr, "%d,%d", &i, &j) != 2) {
	return FTPERR_PASSIVE_ERROR;
    }
    dataAddress.sin_port = htons((i << 8) + j);

    chptr = passReply;
    while (*chptr++) {
	if (*chptr == ',') *chptr = '.';
    }

    if (!inet_pton(AF_INET, passReply, &dataAddress.sin_addr)) 
	return FTPERR_PASSIVE_ERROR;

    dataSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (dataSocket < 0) {
        return FTPERR_FAILED_CONNECT;
    }

    retrCommand = alloca(strlen(remotename) + 20);
    sprintf(retrCommand, "RETR %s\r\n", remotename);
    i = strlen(retrCommand);
   
    if (write(sock, retrCommand, i) != i) {
        return FTPERR_SERVER_IO_ERROR;
    }

    if (connect(dataSocket, (struct sockaddr *) &dataAddress, 
	        sizeof(dataAddress))) {
	close(dataSocket);
        return FTPERR_FAILED_DATA_CONNECT;
    }

    if ((rc = ftpCheckResponse(sock, NULL))) {
	close(dataSocket);
	return rc;
    }

    return dataSocket;
}

int ftpGetFileDone(int sock) {
    if (ftpCheckResponse(sock, NULL)) {
	return FTPERR_BAD_SERVER_RESPONSE;
    }

    return 0;
}

const char *ftpStrerror(int errorNumber, urlprotocol protocol) {
  switch (errorNumber) {
    case FTPERR_BAD_SERVER_RESPONSE:
      return(protocol == URL_METHOD_FTP ? "Bad FTP server response" :
                                          "Bad HTTP server response");

    case FTPERR_SERVER_IO_ERROR:
      return(protocol == URL_METHOD_FTP ? "FTP IO error" : "HTTP IO error");

    case FTPERR_SERVER_TIMEOUT:
      return(protocol == URL_METHOD_FTP ? "FTP server timeout" :
                                          "HTTP server timeout");

    case FTPERR_BAD_HOST_ADDR:
      return(protocol == URL_METHOD_FTP ? "Unable to lookup FTP server host address" :
                                          "Unable to lookup HTTP server host address");

    case FTPERR_BAD_HOSTNAME:
      return(protocol == URL_METHOD_FTP ? "Unable to lookup FTP server host name" :
                                          "Unable to lookup HTTP server host name");

    case FTPERR_FAILED_CONNECT:
      return(protocol == URL_METHOD_FTP ? "Failed to connect to FTP server" :
                                          "Failed to connect to HTTP server");

    case FTPERR_FAILED_DATA_CONNECT:
      return(protocol == URL_METHOD_FTP ? "Failed to establish data connection to FTP server" :
                                          "Failed to establish data connection to HTTP server");

    case FTPERR_FILE_IO_ERROR:
      return("IO error to local file");

    case FTPERR_PASSIVE_ERROR:
      return("Error setting remote server to passive mode");

    case FTPERR_FILE_NOT_FOUND:
      return("File not found on server");

    case FTPERR_TOO_MANY_CONNECTIONS:
      return(protocol == URL_METHOD_FTP ? "Too many connections to FTP server" :
                                          "Too many connections to HTTP server");

    case FTPERR_UNKNOWN:
    default:
      return("Unknown or unexpected error");
  }
}

/* extraHeaders is either NULL or a string with extra headers separated by '\r\n', ending with
 * '\r\n'
 */
int httpGetFileDesc(char * hostname, int port, char * remotename, char *extraHeaders) {
    char * buf;
    struct timeval timeout;
    char headers[4096];
    char * nextChar = headers;
    char *realhost;
    char *hstr;
    int checkedCode;
    struct in_addr serverAddress;
    int sock;
    int rc;
    struct sockaddr_in destPort;
    fd_set readSet;

    realhost = hostname;
    if (port < 0) {
	char *colonptr = strchr(hostname, ':');
	if (colonptr != NULL) {
	    int realhostlen = colonptr - hostname;
	    port = atoi(colonptr + 1);
	    realhost = alloca (realhostlen + 1);
	    memcpy (realhost, hostname, realhostlen);
	    realhost[realhostlen] = '\0';
	} else {
	    port = 80;
	}
    } 

    if ((rc = getHostAddress(realhost, &serverAddress))) return rc;

    sock = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (sock < 0) {
        return FTPERR_FAILED_CONNECT;
    }

    destPort.sin_family = AF_INET;
    destPort.sin_port = htons(port);
    destPort.sin_addr = serverAddress;

    if (connect(sock, (struct sockaddr *) &destPort, sizeof(destPort))) {
	close(sock);
        return FTPERR_FAILED_CONNECT;
    }

    if (extraHeaders)
	hstr = extraHeaders;
    else
	hstr = "";

    buf = alloca(strlen(remotename) + strlen(realhost) + strlen(hstr) + 25);
    sprintf(buf, "GET %s HTTP/1.0\r\nHost: %s\r\n%s\r\n", remotename, realhost, hstr);
    rc = write(sock, buf, strlen(buf));

    /* This is fun; read the response a character at a time until we:

	1) Get our first \r\n; which lets us check the return code
	2) Get a \r\n\r\n, which means we're done */

    *nextChar = '\0';
    checkedCode = 0;
    while (!strstr(headers, "\r\n\r\n")) {
	FD_ZERO(&readSet);
	FD_SET(sock, &readSet);

	timeout.tv_sec = TIMEOUT_SECS;
	timeout.tv_usec = 0;
    
	rc = select(sock + 1, &readSet, NULL, NULL, &timeout);
	if (rc == 0) {
	    close(sock);
	    return FTPERR_SERVER_TIMEOUT;
	} else if (rc < 0) {
	    close(sock);
	    return FTPERR_SERVER_IO_ERROR;
	}

	if (read(sock, nextChar, 1) != 1) {
	    close(sock);
	    return FTPERR_SERVER_IO_ERROR;
	}

	nextChar++;
	*nextChar = '\0';

	if (nextChar - headers == sizeof(headers)) {
	    close(sock);
	    return FTPERR_SERVER_IO_ERROR;
	}

	if (!checkedCode && strstr(headers, "\r\n")) {
	    char * start, * end;

	    checkedCode = 1;
	    start = headers;
	    while (!isspace(*start) && *start) start++;
	    if (!*start) {
		close(sock);
		return FTPERR_SERVER_IO_ERROR;
	    }
	    start++;

	    end = start;
	    while (!isspace(*end) && *end) end++;
	    if (!*end) {
		close(sock);
		return FTPERR_SERVER_IO_ERROR;
	    }

	    *end = '\0';
	    if (!strcmp(start, "404")) {
		close(sock);
		return FTPERR_FILE_NOT_FOUND;
	    } else if (strcmp(start, "200")) {
		close(sock);
		return FTPERR_BAD_SERVER_RESPONSE;
	    }

	    *end = ' ';
	}
    }
    
    return sock;
}

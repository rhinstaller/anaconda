/*
 * ftp.c - ftp code
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 * David Cantrell <dcantrell@redhat.com>
 *
 * Copyright 1997 - 2006 Red Hat, Inc.
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
#include "log.h"
#include "net.h"

static int ftpCheckResponse(int sock, char ** str);
static int getHostAddress(const char * host, void * address, int family);

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
        } else {
            rc = 0;
        }

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
        } else if (!strncmp(errorCode, "550", 3)) {
            return FTPERR_FILE_NOT_FOUND;
        }

        return FTPERR_BAD_SERVER_RESPONSE;
    }

    if (rc) return rc;

    return 0;
}

static int ftpCommand(int sock, char **response, char * command, ...) {
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

    if ((rc = ftpCheckResponse(sock, response)))
        return rc;

    return 0;
}

static int getHostAddress(const char * host, void * address, int family) {
    char *hostname, *port;

    splitHostname((char *) host, &hostname, &port);

    if (family == AF_INET) {
        if (isdigit(host[0])) {
            if (inet_pton(AF_INET, hostname, (struct in_addr *)address) >= 1) {
                return 0;
            } else {
                return FTPERR_BAD_HOST_ADDR;
            }
        } else {
            if (mygethostbyname(hostname, (struct in_addr *)address, AF_INET)) {
                errno = h_errno;
                return FTPERR_BAD_HOSTNAME;
            } else {
                return 0;
            }
        }
    } else if (family == AF_INET6) {
        if (strchr(hostname, ':')) {
            if (inet_pton(AF_INET6, hostname, (struct in_addr6 *)address) >= 1) {
                return 0;
            } else
                return FTPERR_BAD_HOST_ADDR;
        } else {
            /* FIXME: implement me */
            logMessage(ERROR, "we don't have reverse DNS for IPv6 yet");
            return FTPERR_BAD_HOSTNAME;
        }
    } else {
        return FTPERR_UNSUPPORTED_FAMILY;
    }
}

int ftpOpen(char *host, int family, char *name, char *password,
            char *proxy, int port) {
    static int sock;
    struct in_addr addr;
    struct in6_addr addr6;
    struct sockaddr_in destPort;
    struct sockaddr_in6 destPort6;
    struct passwd * pw;
    char * buf;
    int rc = 0;
    char *userReply;

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
        if (asprintf(&buf, "%s@%s", name, host) != -1)
            name = buf;
        host = proxy;
    }

    if (family == AF_INET)
        rc = getHostAddress(host, &addr, AF_INET);
    else if (family == AF_INET6)
        rc = getHostAddress(host, &addr6, AF_INET6);

    if (rc)
        return rc;

    sock = socket(family, SOCK_STREAM, IPPROTO_IP);
    if (sock < 0) {
        return FTPERR_FAILED_CONNECT;
    }

    if (family == AF_INET) {
        destPort.sin_family = family;
        destPort.sin_port = htons(port);
        destPort.sin_addr = addr;

        if (connect(sock, (struct sockaddr *) &destPort, sizeof(destPort))) {
            close(sock);
            return FTPERR_FAILED_CONNECT;
        }
    } else if (family == AF_INET6) {
        destPort6.sin6_family = family;
        destPort6.sin6_port = htons(port);
        destPort6.sin6_addr = addr6;

        if (connect(sock, (struct sockaddr *) &destPort6, sizeof(destPort6))) {
            close(sock);
            return FTPERR_FAILED_CONNECT;
        }
    }

    /* ftpCheckResponse() assumes the socket is nonblocking */
    if (fcntl(sock, F_SETFL, O_NONBLOCK)) {
        close(sock);
        return FTPERR_FAILED_CONNECT;
    }

    if ((rc = ftpCheckResponse(sock, NULL))) {
        return rc;     
    }

    if ((rc = ftpCommand(sock, &userReply, "USER", name, NULL))) {
        close(sock);
        return rc;
    }

    /* FTP does not require that USER be followed by PASS.  Anonymous logins
     * in particular do not need any password.
     */
    if (strncmp(userReply, "230", 3) != 0) {
        if ((rc = ftpCommand(sock, NULL, "PASS", password, NULL))) {
            close(sock);
            return rc;
        }
    }

    if ((rc = ftpCommand(sock, NULL, "TYPE", "I", NULL))) {
        close(sock);
        return rc;
    }

    return sock;
}

/*
 * FTP specification:
 * RFC 959  FILE TRANSFER PROTOCOL (FTP)
 * RFC 2428 FTP Extensions for IPv6 and NATs
 */
int ftpGetFileDesc(int sock, struct in6_addr host, int family,
                   char * remotename) {
    int dataSocket;
    struct sockaddr_in dataAddress;
    struct sockaddr_in6 dataAddress6;
    int i, j;
    char * passReply;
    char * chptr;
    char * retrCommand;
    int rc;

    if (family == AF_INET) {
        if (write(sock, "PASV\r\n", 6) != 6) {
            return FTPERR_SERVER_IO_ERROR;
        }
    } else if (family == AF_INET6) {
        if (write(sock, "EPSV\r\n", 6) != 6) {
            return FTPERR_SERVER_IO_ERROR;
        }
    }

    if ((rc = ftpCheckResponse(sock, &passReply))) {
        return FTPERR_PASSIVE_ERROR;
    }

    /* get IP address and port number from server response */
    if (family == AF_INET) {
        /* we have a PASV response of the form:
         * 227 Entering Passive Mode (209,132,176,30,57,229)
         * where 209.132.176.30 is the IP, and 57 & 229 are the ports
         */
        chptr = passReply;
        while (*chptr && *chptr != '(') chptr++;
        if (*chptr != '(') {
            return FTPERR_PASSIVE_ERROR;
        }
        chptr++;
        passReply = chptr;
        while (*chptr && *chptr != ')') chptr++;
        if (*chptr != ')') {
            return FTPERR_PASSIVE_ERROR;
        }
        *chptr-- = '\0';
        while (*chptr && *chptr != ',') chptr--;
        if (*chptr != ',') {
            return FTPERR_PASSIVE_ERROR;
        }
        chptr--;
        while (*chptr && *chptr != ',') chptr--;
        if (*chptr != ',') {
            return FTPERR_PASSIVE_ERROR;
        }
        *chptr++ = '\0';
    
        /* now passReply points to the IP portion
         * and chptr points to the port number portion
         */
        if (sscanf(chptr, "%d,%d", &i, &j) != 2) {
            return FTPERR_PASSIVE_ERROR;
        }
    } else if (family == AF_INET6) {
        /* we have an EPSV response of the form:
         * 229 Entering Extended Passive Mode (|||51626|)
         * where 51626 is the port
         */
        chptr = passReply;
        while (*chptr && *chptr != '(') chptr++;
        if (*chptr != '(') {
            return FTPERR_PASSIVE_ERROR;
        }
        chptr++;
        while (*chptr && *chptr == '|') chptr++;
        passReply = chptr;
        while (*chptr && *chptr != '|') chptr++;
        *chptr = '\0';
        chptr = passReply;

        /* now chptr contains our port number */
        if (sscanf(chptr, "%d", &i) != 1) {
            return FTPERR_PASSIVE_ERROR;
        }
    }

    /* build our sockaddr */
    if (family == AF_INET) {
        dataAddress.sin_family = family;
        dataAddress.sin_port = htons((i << 8) + j);

        /* passReply contains the IP address, but with commands insteaad of
         * periods, so change those
         */
        chptr = passReply;
        while (*chptr++) {
            if (*chptr == ',') *chptr = '.';
        }

        if (!inet_pton(family, passReply, &dataAddress.sin_addr)) {
            return FTPERR_PASSIVE_ERROR;
        }
    } else if (family == AF_INET6) {
        dataAddress6.sin6_family = family;
        dataAddress6.sin6_port = htons(i);

        /* we don't get this in an EPSV reply, but we got it as a param */
        memset(&dataAddress6.sin6_addr, 0, sizeof(struct in6_addr));
        memcpy(&dataAddress6.sin6_addr, &host, sizeof(host));
    }

    dataSocket = socket(family, SOCK_STREAM, IPPROTO_IP);
    if (dataSocket < 0) {
        return FTPERR_FAILED_CONNECT;
    }

    retrCommand = alloca(strlen(remotename) + 20);
    sprintf(retrCommand, "RETR %s\r\n", remotename);
    i = strlen(retrCommand);
   
    if (write(sock, retrCommand, i) != i) {
        return FTPERR_SERVER_IO_ERROR;
    }

    if (family == AF_INET) {
        if (connect(dataSocket, (struct sockaddr *) &dataAddress, 
            sizeof(dataAddress))) {
            close(dataSocket);
            return FTPERR_FAILED_DATA_CONNECT;
        }
    } else if (family == AF_INET6) {
        if (connect(dataSocket, (struct sockaddr *) &dataAddress6,
            sizeof(dataAddress6))) {
            close(dataSocket);
            return FTPERR_FAILED_DATA_CONNECT;
        }
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
        case FTPERR_PERMISSION_DENIED:
            return(protocol == URL_METHOD_FTP ? "FTP permission denied" :
                                                "HTTP permission denied");

        case FTPERR_BAD_SERVER_RESPONSE:
            return(protocol == URL_METHOD_FTP ? "Bad FTP server response" :
                                                "Bad HTTP server response");

        case FTPERR_SERVER_IO_ERROR:
            return(protocol == URL_METHOD_FTP ? "FTP IO error" :
                                                "HTTP IO error");

        case FTPERR_SERVER_TIMEOUT:
            return(protocol == URL_METHOD_FTP ? "FTP server timeout" :
                                                "HTTP server timeout");

        case FTPERR_BAD_HOST_ADDR:
            return(protocol == URL_METHOD_FTP ?
                "Unable to lookup FTP server host address" :
                "Unable to lookup HTTP server host address");

        case FTPERR_BAD_HOSTNAME:
            return(protocol == URL_METHOD_FTP ?
                "Unable to lookup FTP server host name" :
                "Unable to lookup HTTP server host name");

        case FTPERR_FAILED_CONNECT:
            return(protocol == URL_METHOD_FTP ?
                "Failed to connect to FTP server" :
                "Failed to connect to HTTP server");

        case FTPERR_FAILED_DATA_CONNECT:
            return(protocol == URL_METHOD_FTP ?
                "Failed to establish data connection to FTP server" :
                "Failed to establish data connection to HTTP server");

        case FTPERR_FILE_IO_ERROR:
            return("IO error to local file");

        case FTPERR_PASSIVE_ERROR:
            return("Error setting remote server to passive mode");

        case FTPERR_FILE_NOT_FOUND:
            return("File not found on server");

        case FTPERR_TOO_MANY_CONNECTIONS:
            return(protocol == URL_METHOD_FTP ?
                "Too many connections to FTP server" :
                "Too many connections to HTTP server");

        case FTPERR_UNSUPPORTED_FAMILY:
            return(protocol == URL_METHOD_FTP ?
                "Unsupported address family on FTP server" :
                "Unsupported address family on HTTP server");

        case FTPERR_UNKNOWN:
        default:
            return("Unknown or unexpected error");
    }
}

static int read_headers (char **headers, fd_set *readSet, int sock)
{
    char *nextChar;
    struct timeval timeout;
    int rc;

    *headers = malloc(4096);
    nextChar = *headers;

    *nextChar = '\0';
    while (!strstr(*headers, "\r\n\r\n")) {
        FD_ZERO(readSet);
        FD_SET(sock, readSet);

        timeout.tv_sec = TIMEOUT_SECS;
        timeout.tv_usec = 0;

        rc = select(sock + 1, readSet, NULL, NULL, &timeout);
        if (rc == 0) {
            close(sock);
            free(*headers);
            *headers = NULL;
            return FTPERR_SERVER_TIMEOUT;
        } else if (rc < 0) {
            close(sock);
            free(*headers);
            *headers = NULL;
            return FTPERR_SERVER_IO_ERROR;
        }

        if (read(sock, nextChar, 1) != 1) {
            close(sock);
            free(*headers);
            *headers = NULL;
            return FTPERR_SERVER_IO_ERROR;
        }

        nextChar++;
        *nextChar = '\0';

        if (nextChar - *headers == sizeof(*headers))
            *headers = realloc (*headers, sizeof(*headers)+4096);
    }

    return 0;
}

static char *find_header (char *headers, char *to_find)
{
    char *start, *end, *searching_for, *retval;

    if (asprintf(&searching_for, "\r\n%s:", to_find) == -1)
        return NULL;

    if ((start = strstr(headers, searching_for)) == NULL) {
        free(searching_for);    
        return NULL;
    }

    /* Trim off what we were searching for so we only return the value. */
    start += strlen(searching_for);
    free(searching_for);
    while (isspace(*start) && *start) start++;

    if (start == NULL)
        return NULL;

    /* Now find the end of the header. */
    end = strstr (start, "\r\n");

    if (end == NULL) 
        return NULL;

    retval = strndup (start, end-start);
    return retval;
}

static char *find_status_code (char *headers)
{
    char *start, *end, *retval;

    start = headers;

    /* Skip ahead to the first whitespace in the header. */
    while (!isspace(*start) && *start) start++;
    if (start == NULL)
        return NULL;

    /* Now skip over the whitespace.  What's next is the status code number,
     * followed by a text description of the code.
     */
    while (isspace(*start) && *start) start++;
    if (start == NULL)
        return NULL;

    if ((end = strstr (start, "\r\n")) == NULL)
        return NULL;

    retval = strndup (start, end-start);
    return retval;
}

/* extraHeaders is either NULL or a string with extra headers separated
 * by '\r\n', ending with '\r\n'.
 */
int httpGetFileDesc(char * hostname, int port, char * remotename,
                    char *extraHeaders) {
    char * buf, *headers = NULL;
    char *status;
    char *hstr;
    int family;
    struct in_addr addr;
    struct in6_addr addr6;
    int sock;
    int rc;
    struct sockaddr_in destPort;
    struct sockaddr_in6 destPort6;
    fd_set readSet;

    if (port < 0)
        port = 80;

    family = AF_INET;
    rc = getHostAddress(hostname, &addr, family);
    if (rc) {
        family = AF_INET6;
        rc = getHostAddress(hostname, &addr6, family);
        if (rc)
            return rc;
    }

    sock = socket(family, SOCK_STREAM, IPPROTO_IP);
    if (sock < 0) {
        return FTPERR_FAILED_CONNECT;
    }

    if (family == AF_INET) {
        destPort.sin_family = family;
        destPort.sin_port = htons(port);
        destPort.sin_addr = addr;

        if (connect(sock, (struct sockaddr *) &destPort, sizeof(destPort))) {
            close(sock);
            return FTPERR_FAILED_CONNECT;
        }
    } else if (family == AF_INET6) {
        destPort6.sin6_family = family;
        destPort6.sin6_port = htons(port);
        destPort6.sin6_addr = addr6;

        if (connect(sock, (struct sockaddr *) &destPort6, sizeof(destPort6))) {
            close(sock);
            return FTPERR_FAILED_CONNECT;
        }
    }

    if (extraHeaders)
        hstr = extraHeaders;
    else
        hstr = "";

    buf = alloca(strlen(remotename) + strlen(hostname) + strlen(hstr) + 25);
    sprintf(buf, "GET %s HTTP/1.0\r\nHost: %s\r\n%s\r\n", remotename, hostname, hstr);
    rc = write(sock, buf, strlen(buf));

    rc = read_headers (&headers, &readSet, sock);

    if (rc < 0)
        return rc;

    status = find_status_code (headers);

    if (status == NULL) {
        close(sock);
        return FTPERR_SERVER_IO_ERROR;
    } else if (!strncmp(status, "200", 3)) {
        return sock;
    } else if (!strncmp(status, "301", 3) || !strncmp(status, "302", 3) ||
               !strncmp(status, "303", 3) || !strncmp(status, "307", 3)) {
        struct iurlinfo ui;
        char *redir_loc = find_header (headers, "Location");
        int retval;

        if (redir_loc == NULL) {
            logMessage(WARNING, "got a redirect response, but Location header is NULL");
            close(sock);
            return FTPERR_FILE_NOT_FOUND;
        }

        logMessage(INFO, "redirecting to %s", redir_loc);
        convertURLToUI(redir_loc, &ui);
        retval = httpGetFileDesc (ui.address, -1, ui.prefix, extraHeaders);
        free(redir_loc);
        return retval;
    } else if (!strncmp(status, "403", 3)) {
        close(sock);
        return FTPERR_PERMISSION_DENIED;
    } else if (!strncmp(status, "404", 3)) {
        close(sock);
        return FTPERR_FILE_NOT_FOUND;
    } else {
        close(sock);
        logMessage(ERROR, "bad HTTP response code: %s", status);
        return FTPERR_BAD_SERVER_RESPONSE;
    }
}

/* vim:set shiftwidth=4 softtabstop=4: */

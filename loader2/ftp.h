#ifndef H_FTP
#define H_FTP

#include "urls.h"

const char * ftpStrerror(int ftpErrno, urlprotocol protocol);

#define FTPERR_BAD_SERVER_RESPONSE   -1
#define FTPERR_SERVER_IO_ERROR       -2
#define FTPERR_SERVER_TIMEOUT        -3
#define FTPERR_BAD_HOST_ADDR         -4
#define FTPERR_BAD_HOSTNAME          -5
#define FTPERR_FAILED_CONNECT        -6
#define FTPERR_FILE_IO_ERROR         -7
#define FTPERR_PASSIVE_ERROR         -8
#define FTPERR_FAILED_DATA_CONNECT   -9
#define FTPERR_FILE_NOT_FOUND        -10
#define FTPERR_TOO_MANY_CONNECTIONS  -11
#define FTPERR_BAD_URL               -12
#define FTPERR_TOO_MANY_REDIRECTS    -13
#define FTPERR_UNSUPPORTED_FAMILY    -14
#define FTPERR_PERMISSION_DENIED     -15
#define FTPERR_UNKNOWN               -100

int ftpOpen(char * host, int family, char * name, char * password,
            char * proxy, int port);
int ftpGetFile(int sock, char * remotename, int dest);
int ftpGetFileDesc(int sock, struct in6_addr host, int family,
                   char * remotename);
int ftpGetFileDone(int sock);

int httpGetFileDesc(char * hostname, int port, char * remotename, char *extraHeaders);

#endif

#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdlib.h>

#include "log.h"

int copyFileFd(int infd, char * dest) {
    int outfd;
    char buf[4096];
    int i;
    int rc = 0;

    outfd = open(dest, O_CREAT | O_RDWR, 0666);

    if (outfd < 0) {
	logMessage("failed to open %s: %s", dest, strerror(errno));
	return 1;
    }

    while ((i = read(infd, buf, sizeof(buf))) > 0) {
	if (write(outfd, buf, i) != i) {
	    rc = 1;
	    break;
	}
    }

    close(outfd);

    return rc;
}

int copyFile(char * source, char * dest) {
    int infd = -1;
    int rc;

    infd = open(source, O_RDONLY);

    if (infd < 0) {
	logMessage("failed to open %s: %s", source, strerror(errno));
	return 1;
    }

    rc = copyFileFd(infd, dest);

    close(infd);

    return rc;
}

char * readLine(FILE * f) {
    char buf[1024];

    fgets(buf, sizeof(buf), f);

    /* chop */
    buf[strlen(buf) - 1] = '\0';

    return strdup(buf);
}

int simpleStringCmp(const void * a, const void * b) {
    const char * first = *((const char **) a);
    const char * second = *((const char **) b);

    return strcmp(first, second);
}

char * sdupprintf(const char *format, ...) {
    char *buf = NULL;
    char c;
    va_list ap1;
    size_t size = 0;

    va_start(ap1, format);
    
    /* XXX requires C99 vsnprintf behavior */
    size = vsnprintf(&c, 1, format, ap1) + 1;
    if (size == -1) {
	printf("ERROR: vsnprintf behavior is not C99\n");
	abort();
    }

    va_end(ap1);
    va_start(ap1, format);

    buf = malloc(size);
    if (buf == NULL)
	return NULL;
    vsnprintf(buf, size, format, ap1);
    va_end (ap1);

    return buf;
}

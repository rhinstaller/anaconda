#define MINILIBC_INTERNAL

#include "minilibc.h"

int atexit (void (*__func) (void)) {
    return 0;
}

void exit() {
}

char ** _environ = NULL;
int errno = 0;

void _init (int __status) {
}

void __libc_init_first (int __status) {
}

int
__libc_start_main (int (*main) (int, char **, char **), int argc,
                   char **argv, void (*init) (void), void (*fini) (void),
                   void (*rtld_fini) (void), void *stack_end)
{
    exit ((*main) (argc, argv, NULL));
    /* never get here */
    return 0;
}

void _fini (int __status) {
}

inline int socket(int a, int b, int c) {
    unsigned long args[] = { a, b, c };

    return socketcall(SYS_SOCKET, args);
}

inline int bind(int a, void * b, int c) {
    unsigned long args[] = { a, (long) b, c };

    return socketcall(SYS_BIND, args);
}

inline int listen(int a, int b) {
    unsigned long args[] = { a, b, 0 };

    return socketcall(SYS_LISTEN, args);
}

inline int accept(int a, void * addr, void * addr2) {
    unsigned long args[] = { a, (long) addr, (long) addr2 };

    return socketcall(SYS_ACCEPT, args);
}

int strlen(const char * string) {
    int i = 0;

    while (*string++) i++;

    return i;
}

char * strncpy(char * dst, const char * src, int len) {
    char * chptr = dst;
    int i = 0;

    while (*src && i < len) *dst++ = *src++, i++;
    if (i < len) *dst = '\0';

    return chptr;
}

char * strcpy(char * dst, const char * src) {
    char * chptr = dst;

    while (*src) *dst++ = *src++;
    *dst = '\0';

    return chptr;
}

void * memcpy(void * dst, const void * src, int count) {
    char * a = dst;
    const char * b = src;

    while (count--)
	*a++ = *b++;

    return dst;
}

void sleep(int secs) {
    struct timeval tv;

    tv.tv_sec = secs;
    tv.tv_usec = 0;

    select(0, NULL, NULL, NULL, &tv);
}

int strcmp(const char * a, const char * b) {
    int i, j;  

    i = strlen(a); j = strlen(b);
    if (i < j)
	return -1;
    else if (j < i)
	return 1;

    while (*a && (*a == *b)) a++, b++;

    if (!*a) return 0;

    if (*a < *b)
	return -1;
    else
	return 1;
}

int strncmp(const char * a, const char * b, int len) {
    char buf1[1000], buf2[1000];

    strncpy(buf1, a, len);
    strncpy(buf2, b, len);
    buf1[len] = '\0';
    buf2[len] = '\0';

    return strcmp(buf1, buf2);
}

void printint(int i) {
    char buf[10];
    char * chptr = buf + 9;
    int j = 0;

    if (i < 0) {
	write(1, "-", 1);
	i = -1 * i;
    }

    while (i) {
	*chptr-- = '0' + (i % 10);
	j++;
	i = i / 10;
    }

    write(1, chptr + 1, j);
}

char * strchr(char * str, int ch) {
    char * chptr;

    chptr = str;
    while (*chptr) {
	if (*chptr == ch) return chptr;
	chptr++;
    }

    return NULL;
}

void printf(char * fmt, ...) {
    char buf[2048];
    char * start = buf;
    char * chptr = buf;
    va_list args;
    char * strarg;
    int numarg;

    strcpy(buf, fmt);
    va_start(args, fmt);

    while (start) {
	while (*chptr != '%' && *chptr) chptr++;

	if (*chptr == '%') {
	    *chptr++ = '\0';
	    printstr(start);

	    switch (*chptr++) {
	      case 's': 
		strarg = va_arg(args, char *);
		printstr(strarg);
		break;

	      case 'd':
		numarg = va_arg(args, int);
		printint(numarg);
		break;
	    }

	    start = chptr;
	} else {
	    printstr(start);
	    start = NULL;
	}
    }
}

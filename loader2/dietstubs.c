#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <setjmp.h>
#include <ctype.h>
#include <stdarg.h>
#ifdef GZLIB
#include "../isys/gzlib/gzlib.h"
#endif

#define WLITE_REDEF_STDC 0
#include <wlite_wchar.h>
#include <wlite_wctype.h>

struct glibc_stat {
    long long st_dev;
    unsigned short int __pad1;
    long st_ino;
    int st_mode;
    int st_nlink;
    int  st_uid;
    int  st_gid;
    long long st_rdev;
    unsigned short int __pad2;
    long st_size;
    long st_blksize;
    long st_blocks;
    long st_atime;
    unsigned long int __unused1;
    long st_mtime;
    unsigned long int __unused2;
    long st_ctime;
    unsigned long int __unused3;
    unsigned long int __unused4;
    unsigned long int __unused5;
};

static void stat_copy(struct stat * from, struct glibc_stat * to) {
    to->st_dev = from->st_dev;
    to->st_ino = from->st_ino;
    to->st_mode = from->st_mode;
    to->st_nlink = from->st_nlink;
    to->st_uid = from->st_uid;
    to->st_gid = from->st_gid;
    to->st_rdev = from->st_rdev;
    to->st_size = from->st_size;
    to->st_blksize = from->st_blksize;
    to->st_blocks = from->st_blocks;
    to->st_atime = from->st_atime;
    to->st_mtime = from->st_mtime;
    to->st_ctime = from->st_ctime;
}

int __xstat (int __ver, __const char *__filename, struct glibc_stat * sb) {
    struct stat s;
    int rc = stat(__filename, &s); 

    if (!rc) stat_copy(&s, sb);

    return rc;
}

int __lxstat (int __ver, __const char *__filename, struct glibc_stat * sb) {
    struct stat s;
    int rc = lstat(__filename, &s); 

    if (!rc) stat_copy(&s, sb);

    return rc;
}

int __fxstat (int __ver, int fd, struct glibc_stat * sb) {
    struct stat s;
    int rc = fstat(fd, &s); 

    if (!rc) stat_copy(&s, sb);

    return rc;
}

extern double strtod (__const char * __nptr, char ** __endptr);

double __strtod_internal (__const char *__restrict __nptr,
				 char **__restrict __endptr, int __group) {
    return strtod(__nptr, __endptr);
}


long int __strtol_internal(const char * nptr, char ** endptr, 
			   int base, int group) {
    return strtol(nptr, endptr, base);
}

unsigned long int __strtoul_internal (__const char *__restrict __nptr,
					 char **__restrict __endptr,
					 int __base, int __group) __THROW {
    return strtoul(__nptr, __endptr, __base);
}

char * __strdup(const char * s) {
    return strdup(s);
}

void __assert_fail (__const char *__assertion, __const char *__file,
			   unsigned int __line, __const char *__function) {
    fprintf(stderr, "%s:%d assertion failed in %s()\n",
	    __file, __line, __function);
    abort();
}

int _setjmp(jmp_buf buf) {
    return setjmp(buf);
}

char * strcasestr(char * haystack1, char * needle1) {
    char * haystack = strdup(haystack1);
    char * needle = strdup(needle1);
    char * chptr;

    for (chptr = haystack; *chptr; chptr++) *chptr = toupper(*chptr);
    for (chptr = needle; *chptr; chptr++) *chptr = toupper(*chptr);

    chptr = strstr(needle, haystack);
    if (!chptr) return NULL;

    return (chptr - haystack) + haystack1;
}

int _IO_putc(char c, void * f) {
    return putc(c, f);
}

int _IO_getc(void * f) {
    return getc(f);
}

int __xmknod (int __ver, const char * path, unsigned int mode,
		     long long * dev) {
    return mknod(path, mode, *dev);
}


/* this should print the name of the app, but how? probably in a global
   somewhere (like env is) */
void warn(char * format, ...) {
    va_list args;
    int err = errno;

    va_start(args, format);

    fprintf(stderr, "warning: ");
    vfprintf(stderr, format, args);
    fprintf(stderr, ": %s\n", strerror(err));

    va_end(args);

    errno = err;
}

int pwrite(int fd, const void *buf, size_t count, off_t offset) {
    return __pwrite(fd, buf, count, offset);
}

void * __rawmemchr (void* s, int c) {
    while (*(char *)s != c)
	s++;
    return s;
}

char * dcgettext (const char *domainname, const char *msgid, int category) {
    return msgid;
}

int wcwidth (wchar_t c) {
    return wlite_wcwidth(c);
}

size_t mbrtowc (wchar_t *pwc, const char *s, size_t n, void *ps) {
    return wlite_mbrtowc (pwc, s, n, ps);
}

int iswspace (wchar_t c) {
    return wlite_iswctype((c), wlite_space_);
}

size_t wcrtomb(char *s, wchar_t wc, void *ps) {
    return wlite_wcrtomb (s, wc, ps);
}

/* lie to slang to trick it into using unicode chars for linedrawing */
char *setlocale (int category, const char *locale) {
    if (locale == NULL || *locale == '\0')
	return "en_US.UTF-8";
    return 0;
}

#ifdef GZLIB
void *gzopen(const char *file) {
    return gunzip_open(file);
}

int gzread(void *str, void * buf, int bytes) {
    return gunzip_read(str, buf, bytes);
}

int gzclose(void *str) {
    return gunzip_close(str);
}
#endif

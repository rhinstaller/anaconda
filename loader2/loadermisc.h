#ifndef H_LOADER_MISC_H
#define H_LOADER_MISC_H
#include <stdio.h>
#include <stdarg.h>

int copyFile(char * source, char * dest);
int copyFileFd(int infd, char * dest);
char * readLine(FILE * f);
int simpleStringCmp(const void * a, const void * b);
char * sdupprintf(const char *format, ...) __attribute__ ((format (printf, 1, 2)));
int totalMemory(void);

#endif

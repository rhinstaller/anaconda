#ifndef H_LOADER_MISC_H
#define H_LOADER_MISC_H

int copyFile(char * source, char * dest);
int copyFileFd(int infd, char * dest);
char * readLine(FILE * f);
int simpleStringCmp(const void * a, const void * b);

#endif

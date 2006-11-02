#ifndef H_DNS
#define H_DNS 

#include <netinet/in.h>

int mygethostbyname(char * name, void * addr, int family);
char * mygethostbyaddr(char * ipnum, int family);

#endif

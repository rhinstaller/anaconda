#ifndef H_DNS
#define H_DNS 

#include <netinet/in.h>

int mygethostbyname(char * name, struct in_addr * addr);
char * mygethostbyaddr(char * ipnum);

#endif

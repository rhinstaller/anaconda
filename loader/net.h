#ifndef H_LOADER_NET
#define H_LOADER_NET

int readNetConfig(char * device, struct pumpNetIntf * dev, int flags);
int nfsGetSetup(char ** hostptr, char ** dirptr);

#endif

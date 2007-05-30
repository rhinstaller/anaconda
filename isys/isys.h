#ifndef H_ISYS
#define H_ISYS

#define MIN_RAM			64000	    
#define MIN_GUI_RAM		192000
#if defined(__x86_64__) || defined(__ia64__) || defined(__s390x__) || defined(__ppc64__)
#define EARLY_SWAP_RAM		400000
#else
#define EARLY_SWAP_RAM		270000
#endif

/* returns -2 for errno, -1 for unknown device */
int devMakeInode(char * devName, char * path);

int insmod(char * modName, char * path, char ** args);
int rmmod(char * modName);

/* returns 0 for true, !0 for false */
int fileIsIso(const char * file);

/* returns 1 if on an iSeries vio console, 0 otherwise */
int isVioConsole(void);

/* dasd functions */
char *getDasdPorts();
int isLdlDasd(char * dev);
int isUsableDasd(char *device);

#endif

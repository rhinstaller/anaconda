#ifndef H_ISYS
#define H_ISYS

#define MIN_ROOTPART_SIZE_MB	250

#define MIN_RAM			17000	    /* 20M or so */
#define MIN_GUI_RAM		48000
#define EARLY_SWAP_RAM		72000

/* returns -2 for errno, -1 for unknown device */
int devMakeInode(char * devName, char * path);

int insmod(char * modName, char * path, char ** args);
int rmmod(char * modName);

/* returns 0 for true, !0 for false */
int fileIsIso(const char * file);

/* returns 1 if on an iSeries vio console, 0 otherwise */
int isVioConsole(void);

#endif

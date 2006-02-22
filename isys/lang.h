#ifndef ISYS_LANG_H
#define ISYS_LANG_H

#include "stubs.h"

/* define ask johnsonm@redhat.com where this came from */
#define KMAP_MAGIC 0x8B39C07F
#define KMAP_NAMELEN 40         /* including '\0' */

struct kmapHeader {
    int magic;
    int numEntries;
};
        
struct kmapInfo {
    int size;
    char name[KMAP_NAMELEN];
};

int loadKeymap(gzFile stream);
int isysLoadFont(void);
int isysLoadKeymap(char * keymap);
int isysSetUnicodeKeymap(void);

#endif

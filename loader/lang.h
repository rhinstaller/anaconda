#ifndef _LANG_H_
#define _LANG_H_

#define _(x) translateString (x)
#define N_(foo) (foo)

int chooseLanguage(char ** lang, int flags);
int chooseKeyboard(char ** keymap, char ** kbdtypep, int flags);
char * translateString(char * str);
void setLanguage (char * key, int flags);

/* define ask johnsonm@redhat.com where this came from */
#define KMAP_MAGIC 0x8B39C07F
#define KMAP_NAMELEN 40		/* including '\0' */

struct kmapHeader {
    int magic;
    int numEntries;
};

struct kmapInfo {
    int size;
    char name[KMAP_NAMELEN];
};


#endif /* _LANG_H_ */

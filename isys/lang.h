#ifndef ISYS_LANG_H
#define ISYS_LANG_H

#include "stubs.h"

int loadKeymap(gzFile stream);
int isysLoadFont(char * fontFile);
int isysLoadKeymap(char * keymap);

#endif

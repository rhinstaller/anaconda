#ifndef H_DIALOGBOXES
#define H_DIALOGBOXES

#include "popt.h"

#define MSGBOX_MSG 0 
#define MSGBOX_YESNO 1
#define MSGBOX_INFO 2

#define FLAG_NOITEM 		(1 << 0)
#define FLAG_NOCANCEL 		(1 << 1)
#define FLAG_SCROLL_TEXT 	(1 << 2)
#define FLAG_DEFAULT_NO 	(1 << 3)

#define DLG_ERROR		-1
#define DLG_OKAY		0
#define DLG_CANCEL		1

int messageBox(const char * text, int height, int width, int type, int flags);
int checkList(const char * text, int height, int width, poptContext optCon,
		int useRadio, int flags, char *** selections);
int listBox(const char * text, int height, int width, poptContext optCon,
		int flags, char ** result);
int inputBox(const char * text, int height, int width, poptContext optCon, 
		int flags, char ** result);
int gauge(const char * text, int height, int width, poptContext optCon, int fd, 
		int flags);
void useFullButtons(int state);

#endif

#ifndef _WINDOWS_H_
#define _WINDOWS_H_

#include "lang.h"

void winStatus(int width, int height, char * title, char * text, ...);
void scsiWindow(const char * driver);

#define errorWindow(String) \
	newtWinMessage(_("Error"), _("OK"), String, strerror (errno));

#endif /* _WINDOWS_H_ */

#include <errno.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

#include "windows.h"
#include "lang.h"

void winStatus(int width, int height, char * title,
		char * text, ...) {
    newtComponent t, f;
    char * buf = NULL;
    int size = 0;
    int i = 0;
    va_list args;

    va_start(args, text);

    do {
	size += 1000;
	if (buf) free(buf);
	buf = malloc(size);
	i = vsnprintf(buf, size, text, args);
    } while (i == size);

    va_end(args);

    newtCenteredWindow(width, height, title);

    t = newtTextbox(1, 1, width - 2, height - 2, NEWT_TEXTBOX_WRAP);
    newtTextboxSetText(t, buf);
    f = newtForm(NULL, NULL, 0);

    free(buf);

    newtFormAddComponent(f, t);

    newtDrawForm(f);
    newtRefresh();
    newtFormDestroy(f);
}

void scsiWindow(char * driver) {
    winStatus(40, 3, _("Loading SCSI driver"), 
	      _("Loading %s driver..."), driver);
}

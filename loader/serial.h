#include <termios.h>
#include <unistd.h>

#include <glib.h>

void get_mode_and_flags(struct termios *cmode, int *flags);
void set_mode(struct termios *cmode);
void restore_console(struct termios *orig_cmode, int orig_flags);
void init_serial(struct termios *orig_cmode, int *orig_flags, GHashTable *cmdline);

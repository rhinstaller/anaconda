#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <curses.h>
#include <term.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/time.h>

void
cleanup()
{
    putp(from_status_line);
    putp(dis_status_line);
    exit(0);
}

void
main(int argc, char *argv[])
{
    char *term, *mail, *p, *buff;
    time_t interval=10000000;
    time_t old_mtime=0;
    int n, update=1;
    struct stat st;

    if ((term = getenv("TERM")) == NULL
	|| (mail = getenv("MAIL")) == NULL) exit(1);
    setupterm(term, 1, &n);
    if (n != 1) exit(1);
    if (!has_status_line) exit(1);
    if ((buff = calloc(columns + 1, 1)) == NULL) exit(1);
    putp(tparm(to_status_line, 0, 0));
    putp(from_status_line);
    fflush(stdout);
    signal(SIGINT, cleanup);
    signal(SIGKILL, cleanup);
    while (1) {
	if (!stat(mail, &st) && st.st_size) {
	    if (st.st_mtime > old_mtime) {
		sprintf(buff, "New mail received %s",
			ctime(&st.st_mtime));
		update = 1;
		old_mtime = st.st_mtime;
	    }
	} else {
	    if (st.st_mtime > old_mtime) {
		sprintf(buff, "No mail");
		update = 1;
		old_mtime = st.st_mtime;
	    }
	}
	if (update) {
	    if ((p = strchr(buff, '\n')) != NULL) *p = 0;
	    printf("%s%s\n%*s%s%s",
		   tparm(to_status_line, 0, 0),
		   enter_standout_mode,
		   columns, buff,
		   exit_standout_mode,
		   from_status_line);
	    fflush(stdout);
	    update = 0;
	}
	usleep(interval);
    }
    cleanup();
}

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <zlib.h>
#include <fcntl.h>
#include <sys/utsname.h>
#include <sys/wait.h>

#include "cpio.h"
#include "isys.h"

/* hack */
int insmod_main(int argc, char ** argv);
int rmmod_main(int argc, char ** argv);

int ourInsmodCommand(int argc, char ** argv) {
    char * file;
    char finalName[100];
    char * chptr;
    FD_t fd;
    int rc, rmObj = 0;
    int sparc64 = 0;
#ifdef __sparc__

    struct utsname u;

    if (!uname(&u) && !strcmp(u.machine, "sparc64"))
       sparc64 = 1;
#endif

    if (argc < 2) {
	fprintf(stderr, "usage: insmod <module>.o [params]\n");
	return 1;
    }

    file = argv[1];
    if (access(file, R_OK)) {
	/* it might be having a ball */
	fd = fdOpen(sparc64 ?
		    "/modules/modules64.cgz" : "/modules/modules.cgz",
		    O_RDONLY, 0);
	if (fdFileno(fd) < 0) {
	    return 1;
	}

	chptr = strrchr(file, '/');
	if (chptr) file = chptr + 1;
	sprintf(finalName, "/tmp/%s", file);

	if (installCpioFile(fd, file, finalName, 0))
	    return 1;

	rmObj = 1;
	file = finalName;
    }

    argv[1] = file;

#ifdef __sparc__
    if (sparc64) {
       int pid, status;
       
       if (!(pid = fork())) {
           execv("/bin/insmod64", argv);
           exit(-1);
       }
       waitpid(pid, &status, 0);
       if (WIFEXITED(status))
           rc = WEXITSTATUS(status);
       else
           rc = -1;
    } else
#endif
       rc = insmod_main(argc, argv);
    
    if (rmObj) unlink(file);

    return rc;
}

int rmmod(char * modName) {
    pid_t child;
    int status;
    char * argv[] = { "/bin/rmmod", modName, NULL };
    int argc = 2;
    int rc = 0;

    if ((child = fork()) == 0) {
	exit(rmmod_main(argc, argv));
    }

    waitpid(child, &status, 0);

    if (WIFEXITED(status))
       rc = WEXITSTATUS(status);
    else
       rc = -1;

    return rc;
}

int insmod(char * modName, char ** args) {
    int argc;
    char ** argv;
    int rc = 0;
    pid_t child;
    int status;

    argc = 2;
    for (argv = args; argv && *argv; argv++, argc++);

    argv = malloc(sizeof(*argv) * (argc + 1));
    argv[0] = "/bin/insmod";
    argv[1] = modName;
    if (args)
	memcpy(argv + 2, args, argc - 1);

    if ((child = fork()) == 0) {
	exit(ourInsmodCommand(argc, argv));
    }

    waitpid(child, &status, 0);

    if (WIFEXITED(status))
       rc = WEXITSTATUS(status);
    else
       rc = -1;

    return rc;
}

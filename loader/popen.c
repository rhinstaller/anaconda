#include <errno.h>
#include <fcntl.h>
#include <popt.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>

#include <syslog.h>

struct req {
    FILE * f;
    pid_t child;
};

struct req lastRequest = { NULL, -1 };

FILE * popen(const char * command, const char * type) {
    char ** argv;
    int argc;
    int p[2];
    pid_t child;

    if (strcmp(type, "r") || lastRequest.f)
	return NULL;

    if (poptParseArgvString(command, &argc, (const char ***) &argv)) {
	return NULL;
    }

    pipe(p);

    if (!(child = fork())) {
	int i;
	char ** args;

	close(p[0]);
	dup2(p[1], 1);
	dup2(p[1], 2);
	close(p[1]);

	args = malloc(sizeof(*args) * (argc + 1));
	for (i = 0; i < argc; i++) {
	    args[i] = argv[i];
	}

	args[argc] = NULL;

	execv("/sbin/insmod", args);
	exit(1);
    }

    free(argv);

    close(p[1]);

    lastRequest.f = fdopen(p[0], "r");
    lastRequest.child = child;

    return lastRequest.f;
}

int pclose(FILE * stream) {
    int status;

    if (stream != lastRequest.f) return -1;

    fclose(stream);
    
    waitpid(lastRequest.child, &status, 0);
    lastRequest.f = NULL;

    return status;
}

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <asm/page.h>
#include <sys/swap.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include <zlib.h>

#include "../isys/imount.h"
#include "../isys/isys.h"

#include "commands.h"
#include "idmap.h"
#include "ls.h"
#include "popt.h"

static int copyfd(int to, int from);

static int copyfd(int to, int from) {
    char buf[1024];
    int size;

    while ((size = read(from, buf, sizeof(buf))) > 0) {
	if (write(to, buf, size) != size) {
	    fprintf(stderr, "error writing output: %s\n", strerror(errno));
	    return 1;
	}
    }

    if (size < 0) {
	fprintf(stderr, "error reading input: %s\n", strerror(errno));
	return 1;
    }

    return 0;
}

static int catFile(char * filename) {
    int fd;
    int rc;

    fd = open(filename, O_RDONLY);
    if (fd < 0) {
	fprintf(stderr, "cannot open %s: %s\n", filename, strerror(errno));
	return 1;
    }

    rc = copyfd(1, fd);
    close(fd);

    return rc;
}

int catCommand(int argc, char ** argv) {
    char ** argptr = argv + 1;
    int rc;

    if (!*argptr) {
	return copyfd(1, 0);
    } else {
	while (*argptr) {
	    rc = catFile(*argptr);
	    if (rc) return rc;
	    argptr++;
	}
    }

    return 0;
}

int lsmodCommand(int argc, char ** argv) {
    puts("Module:        #pages:  Used by:");
    catFile("/proc/modules");

    return 0;
}

#define MOUNT_USAGE fprintf(stderr, "usage: mount -t <fs> <device> <dir>\n" \
			"       (if /dev/ is left off the device name, a " \
			"temporary node will be created)\n")

int mountCommand(int argc, char ** argv) {
    char * dev, * dir;
    char * fs;

    if (argc < 2) {
	return catFile("/proc/mounts");
    } else if (argc == 3) {
	if (strchr(argv[1], ':'))
	    fs = "nfs";
	else
	    fs = "ext2";
	dev = argv[1];
	dir = argv[2];
    } else if (argc != 5) {
	MOUNT_USAGE;
	return 1;
    } else {
	if (strcmp(argv[1], "-t")) {
	    MOUNT_USAGE;
	    return 1;
	}
	
	fs = argv[2];
	dev = argv[3];
	dir = argv[4];

    }

    if (!strncmp(dev, "/dev/", 5) && access(dev, X_OK)) 
	dev += 5;

    if (doPwMount(dev, dir, fs, 0, 1, NULL, NULL))
	return 1;

    return 0;
}

int umountCommand(int argc, char ** argv) {
    if (argc != 2) {
	fprintf(stderr, "umount expects a single argument\n");
	return 1;
    }

    if (umount(argv[1])) {
	fprintf(stderr, "error unmounting %s: %s\n", argv[1], strerror(errno));
	return 1;
    }

    return 0;
}

int mkdirCommand(int argc, char ** argv) {
    char ** argptr = argv + 1;

    if (argc < 2) {
	fprintf(stderr, "umount expects one or more arguments\n");
	return 1;
    }

    while (*argptr) {
	if (mkdir(*argptr, 0755)) {
	    fprintf(stderr, "error creating directory %s: %s\n", *argptr,
			strerror(errno));
	    return 1;
	}

	argptr++;
    }

    return 0;
}

int mknodCommand(int argc, char ** argv) {
    int major, minor;
    char * path;
    int mode = 0600;
    char *end;

    if (argc != 5 && argc != 2) {
	fprintf(stderr, "usage: mknod <path> [b|c] <major> <minor> or mknod <path>\n");
	return 1;
    }

    path = argv[1];

    if (argc == 2) {
	end = path + strlen(path) - 1;
	while (end > path && *end != '/') end--;

	if (devMakeInode(end, path)) {
	    return 1;
	}

	return 0;
    }

    if (!strcmp(argv[2], "b")) 
	mode |= S_IFBLK;
    else if (!strcmp(argv[2], "c"))
	mode |= S_IFCHR;
    else {
	fprintf(stderr, "unknown node type %s\n", argv[2]);
	return 1;
    } 

    major = strtol(argv[3], &end, 0);
    if (*end) {
	fprintf(stderr, "bad major number %s\n", argv[3]);
	return 1;
    }

    minor = strtol(argv[4], &end, 0);
    if (*end) {
	fprintf(stderr, "bad minor number %s\n", argv[4]);
	return 1;
    }

    if (mknod(path, mode, makedev(major, minor))) {
	fprintf(stderr, "mknod failed: %s\n", strerror(errno));
	return 1;
    }

    return 0;
}

int lnCommand(int argc, char ** argv) {
    char ** argptr = argv + 1;
    int force = 0, soft = 0;
    int rc;

    while (*argptr && **argptr == '-') {
	if (!strcmp(*argptr, "-f"))
	   force = 1;
	else if (!strcmp(*argptr, "-s"))
	   soft = 1;
	else if (!strcmp(*argptr, "-fs") || !strcmp(*argptr, "-sf"))
	   force = soft = 1;
	else {
	   fprintf(stderr, "ln: unknown argument %s\n", *argptr);
	   return 1;
	}

	argptr++;
    }

    if (!*argptr || !(*argptr + 1) || *(argptr + 2)) {
	fprintf(stderr, "ln requires exactly two filenames\n");
	return 1;
    }

    if (force) unlink(*(argptr + 1));
    if (soft)
	rc = symlink(*argptr, *(argptr + 1));
    else
	rc = link(*argptr, *(argptr + 1));

    if (rc) {
	perror("error");
	return 1;
    }

    return 0;
}

int rmCommand(int argc, char ** argv) {
    char ** argptr = argv + 1;

    if (argc < 2) {
	fprintf(stderr, "rm expects one or more arguments "
		"(no flags are supported");
	return 1;
    }

    while (*argptr) {
	if (unlink(*argptr)) {
	    fprintf(stderr, "unlink of %s failed: %s\n", *argptr, 
			strerror(errno));
	    return 1;
	}

	argptr++;
    }

    return 0;
}

int chmodCommand(int argc, char ** argv) {
    char ** argptr = argv + 2;
    int mode;
    char * end;

    if (argc < 3) {
	fprintf(stderr, "usage: chmod <mode> <one or files>\n");
	return 1;
    }

    mode = strtol(argv[1], &end, 8);
    if (*end) {
	fprintf(stderr, "illegal mode %s\n", argv[1]);
	return 1;
    }

    while (*argptr) {
	if (chmod(*argptr, mode)) {
	    fprintf(stderr, "error in chmod of %s to 0%o: %s\n", *argptr,
			mode, strerror(errno));
	    return 1;
	}

	argptr++;
    }

    return 0;
}

int uncpioCommand(int argc, char ** argv) {
    int rc;
    char * fail;

    if (argc != 1) {
	fprintf(stderr, "uncpio reads from stdin");
	return 1;
    }

    rc = cpioInstallArchive(gzdopen(0, "r"), NULL, 0, NULL, NULL, &fail);
    return (rc != 0);
}

int lsCommand(int argc, char ** argv) {
    poptContext optCon;
    int flags = 0;
    int rc;
    char path[1024];
    struct poptOption ksOptions[] = {
	{ NULL, 'l', 0, NULL, 'l' },
	{ NULL, 'C', 0, NULL, 'C' },
	{ NULL, 'd', 0, NULL, 'd' },
	{ NULL, 'g', 0, NULL, 'g' },
	{ NULL, 'n', 0, NULL, 'n' },
	{ NULL, 'p', 0, NULL, 'p' },
	{ NULL, 'a', 0, NULL, 'a' },
	{ NULL, 'L', 0, NULL, 'L' },
	{ NULL, 'f', 0, NULL, 'f' },
	{ NULL, 'r', 0, NULL, 'r' },
	{ NULL, 't', 0, NULL, 't' },
	{ NULL, 'S', 0, NULL, 'S' },
	{ NULL, 'R', 0, NULL, 'R' },
	{ NULL, '\0', 0, NULL, '\0' }
    };

    optCon = poptGetContext(NULL, argc, argv, ksOptions, 0);
    if (isatty(1)) flags |= SENDDIR_MULTICOLUMN;

    while ((rc = poptGetNextOpt(optCon)) >= 0) {
	switch (rc) {
	  case 'l':
	    flags |= SENDDIR_LONG; flags &= ~SENDDIR_MULTICOLUMN;
	    break;
	  case 'C':
	    flags |= SENDDIR_MULTICOLUMN; flags &= ~SENDDIR_LONG;
	    break;
	  case 'd': flags |= SENDDIR_SIMPLEDIRS; 	break;
	  case 'g': /* ignored */ 			break;
	  case 'n': flags |= SENDDIR_NUMIDS; 		break;
	  case 'p': case 'F': flags |= SENDDIR_FILETYPE; break;
	  case 'a': flags |= SENDDIR_ALL; 		break;
	  case 'L': flags |= SENDDIR_FOLLOWLINKS; 	break;
	  case 'f': flags |= SENDDIR_SORTNONE; 		break;
	  case 'r': flags |= SENDDIR_SORTREVERSE; 	break;
	  case 't': flags |= SENDDIR_SORTMTIME; 	break;
	  case 'S': flags |= SENDDIR_SORTSIZE; 		break;
	  case 'R': flags |= SENDDIR_RECURSE; 		break;
	}
    }

    getcwd(path, 1000);

    if (rc < -1) {
	fprintf(stderr, "argument error: %s %s",
		   poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		   poptStrerror(rc));
    } else {
	idInit();

	argv = poptGetArgs(optCon);
	if (argv) {
	    while (*argv) {
		if (argv[0][0] == '/')
		    listFiles("", *argv, flags);
		else
		    listFiles(path, *argv, flags);
		argv++;
	    }
	} else {
	    listFiles(path, "", flags);
	}
    }

    return 0;
}

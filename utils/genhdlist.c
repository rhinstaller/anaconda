#include <alloca.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <glob.h>
#include <dirent.h>
#include <popt.h>
#include <rpmlib.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define FILENAME_TAG 1000000
#define FILESIZE_TAG 1000001
#define CDNUM_TAG    1000002

int onePass(FD_t outfd, const char * dirName, int cdNum) {
    FD_t fd;
    struct dirent * ent;
    char * subdir = alloca(strlen(dirName) + 20);
    int errno;
    Header h;
    int isSource, rc;
    int_32 size;
    DIR * dir;
    struct stat sb;

    sprintf(subdir, "%s/RedHat/RPMS", dirName);

    dir = opendir(subdir);
    if (!dir) {
	fprintf(stderr,"error opening directory %s: %s\n", subdir,
		strerror(errno));
	return 1;
    }

    chdir(subdir);

    errno = 0;
    ent = readdir(dir);
    if (errno) {
	perror("readdir");
	return 1;
    }

    while (ent) {
       int i = strlen (ent->d_name);
       if (i > 4 && strcasecmp (&ent->d_name [i - 4], ".rpm") == 0) {
	    fd = Fopen(ent->d_name, "r");

	    if (!fd) {
		perror("open");
		exit(1);
	    }

	    if (stat(ent->d_name, &sb)) {
		perror("stat");
		exit(1);
	    }
	    size = sb.st_size;

	    rc = rpmReadPackageHeader(fd, &h, &isSource, NULL, NULL);

	    if (!rc) {
  	        headerRemoveEntry(h, RPMTAG_POSTIN);
		headerRemoveEntry(h, RPMTAG_POSTUN);
		headerRemoveEntry(h, RPMTAG_PREIN);
		headerRemoveEntry(h, RPMTAG_PREUN);
		headerRemoveEntry(h, RPMTAG_FILEUSERNAME);
		headerRemoveEntry(h, RPMTAG_FILEGROUPNAME);
		headerRemoveEntry(h, RPMTAG_FILEVERIFYFLAGS);
		headerRemoveEntry(h, RPMTAG_FILERDEVS);
		headerRemoveEntry(h, RPMTAG_FILEMTIMES);
		headerRemoveEntry(h, RPMTAG_FILEDEVICES);
		headerRemoveEntry(h, RPMTAG_FILEINODES);
		headerRemoveEntry(h, RPMTAG_TRIGGERSCRIPTS);
		headerRemoveEntry(h, RPMTAG_TRIGGERVERSION);
		headerRemoveEntry(h, RPMTAG_TRIGGERFLAGS);
		headerRemoveEntry(h, RPMTAG_TRIGGERNAME);
		headerRemoveEntry(h, RPMTAG_CHANGELOGTIME);
		headerRemoveEntry(h, RPMTAG_CHANGELOGNAME);
		headerRemoveEntry(h, RPMTAG_CHANGELOGTEXT);
		headerRemoveEntry(h, RPMTAG_ICON);
		headerRemoveEntry(h, RPMTAG_GIF);
		headerRemoveEntry(h, RPMTAG_VENDOR);
		headerRemoveEntry(h, RPMTAG_EXCLUDE);
		headerRemoveEntry(h, RPMTAG_EXCLUSIVE);
		headerRemoveEntry(h, RPMTAG_DISTRIBUTION);
		headerRemoveEntry(h, RPMTAG_VERIFYSCRIPT);
		headerAddEntry(h, FILENAME_TAG, RPM_STRING_TYPE, ent->d_name, 1);
		headerAddEntry(h, FILESIZE_TAG, RPM_INT32_TYPE, 
				&size, 1);

		if (cdNum > -1)
		    headerAddEntry(h, CDNUM_TAG, RPM_INT32_TYPE, 
				    &cdNum, 1);

		headerWrite(outfd, h, HEADER_MAGIC_YES);
		headerFree(h);
	    }
	    Fclose(fd);
	}

	errno = 0;
	ent = readdir(dir);
	if (errno) {
	    perror("readdir");
	    return 1;
	}
    } 

    closedir(dir);

    return 0;
}

static void usage(void) {
    fprintf(stderr, "genhdlist:		genhdlist [--withnumbers] [--hdlist <path>] <paths>+\n");
    exit(1);
}

int main(int argc, const char ** argv) {
    char buf[300];
    FD_t outfd;
    int cdNum = -1;
    const char ** args;
    int doNumber = 0;
    int rc;
    char * hdListFile = NULL;
    poptContext optCon;
    struct poptOption options[] = {
            { "hdlist", '\0', POPT_ARG_STRING, &hdListFile, 0 },
            { "withnumbers", '\0', 0, &doNumber, 0 },
            { 0, 0, 0, 0, 0 }
    };

    optCon = poptGetContext("genhdlist", argc, argv, options, 0);
    poptReadDefaultConfig(optCon, 1);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "%s: bad argument %s: %s\n", "genhdlist",
		poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		poptStrerror(rc));
	return 1;
    }

    args = poptGetArgs(optCon);
    if (!args || !args[0] || !args[0][0])
	usage();

    if (!hdListFile) {
	strcpy(buf, args[0]);
	strcat(buf, "/RedHat/base/hdlist");
	hdListFile = buf;
    }

    unlink(hdListFile);
    
    outfd = Fopen(hdListFile, "w");
    if (!outfd) {
	fprintf(stderr,"error creating file %s: %s\n", buf, strerror(errno));
	return 1;
    }

    if (doNumber)
	cdNum = 1;

    while (args[0]) {
	if (onePass(outfd, args[0], cdNum))
	    return 1;
	if (doNumber) cdNum++;
	args++;
    }

    Fclose(outfd);

    poptFreeContext(optCon);

    return 0;
}

#include <alloca.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <glob.h>
#include <dirent.h>
#include <rpmlib.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define FILENAME_TAG 1000000
#define FILESIZE_TAG 1000001

int tags[] =  { RPMTAG_NAME, RPMTAG_VERSION, RPMTAG_RELEASE, RPMTAG_SERIAL,
		RPMTAG_COMPFILEDIRS, RPMTAG_COMPFILELIST, RPMTAG_COMPDIRLIST,
		RPMTAG_FILESIZES, RPMTAG_GROUP, RPMTAG_REQUIREFLAGS, 
		RPMTAG_REQUIRENAME, RPMTAG_REQUIREVERSION, RPMTAG_DESCRIPTION, 
		RPMTAG_SUMMARY, RPMTAG_PROVIDES, RPMTAG_SIZE, 
		RPMTAG_OBSOLETES };
int numTags = sizeof(tags) / sizeof(int);

int main(int argc, char ** argv) {
    char buf[300];
    DIR * dir;
    FD_t outfd, fd;
    struct dirent * ent;
    int rc, isSource;
    Header h;
    struct stat sb;
    int_32 size;

    if (argc < 2 || argc > 3) {
	fprintf(stderr, "usage: genhdlist <dir>\n");
	exit(1);
    }

    if (*argv[1] != '/') {
        getcwd(buf, 300);
        strcat(buf, "/");
        strcat(buf, argv[1]);
    } else 
        strcpy(buf, argv[1]);

    strcat(buf, "/RedHat/RPMS");

    dir = opendir(buf);
    if (!dir) {
	fprintf(stderr,"error opening directory %s: %s\n", buf,
		strerror(errno));
	return 1;
    }
    chdir(buf);

    strcat(buf, "/../base/hdlist");
    if (argv[2] && *argv[2])
	strcpy(buf, argv[2]);

    unlink(buf);
    
    outfd = Fopen(buf, "w");
    if (!outfd) {
	fprintf(stderr,"error creating file %s: %s\n", buf, strerror(errno));
	return 1;
    }

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
		headerWrite(outfd, h, HEADER_MAGIC_YES);
		headerFree(h);
	    }
	    fdio->close(fd);
	}

	errno = 0;
	ent = readdir(dir);
	if (errno) {
	    perror("readdir");
	    return 1;
	}
    } 

    closedir(dir);
    fdio->close(outfd);

    return 0;
}

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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define FILENAME_TAG 1000000
#define FILESIZE_TAG 1000001
#define CDNUM_TAG    1000002
#define ORDER_TAG    1000003

struct onePackageInfo {
    char * name;
    char * arch;
};

int pkgInfoCmp(const void * a, const void * b) {
    const struct onePackageInfo * one = a;
    const struct onePackageInfo * two = b;
    int i;

    i = strcmp(one->name, two->name);
    if (i) return i;

    return strcmp(one->arch, two->arch);
}

struct onePackageInfo * pkgList;
int pkgListItems = 0;
int pkgListAlloced = 0;
char ** depOrder = NULL;

/* mmmm... linear search */
int getOrder (char * fn)
{
    char *p;
    int i;

    if (!depOrder || !depOrder[0] || !depOrder[0][0]) {
	return -1;
    }

    i = 0;
    p = depOrder[i];
    while (p && *p && strncmp (fn, p, strlen(p))) {
	p = depOrder[++i];
    } 
    
    if (p) {
	return i - 1;
    }

    return -1;
}

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
    int_32 * fileSizes;
    int fileCount;
    int order = 0;

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
		if (pkgListItems == pkgListAlloced) {
		    pkgListAlloced += 100;
		    pkgList = realloc(pkgList, 
				      sizeof(*pkgList) * pkgListAlloced);
		}

		headerGetEntry(h, RPMTAG_NAME, NULL, 
			       (void **) &pkgList[pkgListItems].name, NULL);
		headerGetEntry(h, RPMTAG_ARCH, NULL, 
			       (void **) &pkgList[pkgListItems].arch, NULL);

		pkgList[pkgListItems].name = strdup(pkgList[pkgListItems].name);
		pkgList[pkgListItems].arch = strdup(pkgList[pkgListItems].arch);
		pkgListItems++;

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

		/* Recaclulate the package size based on a 4k block size */
		if (headerGetEntry(h, RPMTAG_FILESIZES, NULL, 
				   (void **) &fileSizes, &fileCount)) {
		    int fileNum;
		    int newSize = 0;
		    int * p;

		    for (fileNum = 0; fileNum < fileCount; fileNum++)
			newSize += ((fileSizes[fileNum] + 4093) / 4096) * 4096;

		    headerGetEntry(h, RPMTAG_SIZE, NULL, (void **) &p, NULL);

		    headerRemoveEntry(h, RPMTAG_SIZE);
		    headerAddEntry(h, RPMTAG_SIZE, RPM_INT32_TYPE, 
				    &newSize, 1);
		}

		if (cdNum > -1)
		    headerAddEntry(h, CDNUM_TAG, RPM_INT32_TYPE, 
				    &cdNum, 1);

		if ((order = getOrder (ent->d_name)) > -1) {
		    headerAddEntry(h, ORDER_TAG, RPM_INT32_TYPE, 
				    &order, 1);
		}

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
    fprintf(stderr, "genhdlist:		genhdlist [--withnumbers] [--pkgorder <path>] [--hdlist <path>] <paths>+\n");
    exit(1);
}

int main(int argc, const char ** argv) {
    char buf[300];
    FD_t outfd;
    int cdNum = -1;
    const char ** args;
    int doNumber = 0;
    int rc;
    int i;
    char * hdListFile = NULL;
    char * depOrderFile = NULL;
    poptContext optCon;
    struct poptOption options[] = {
            { "hdlist", '\0', POPT_ARG_STRING, &hdListFile, 0 },
            { "withnumbers", '\0', 0, &doNumber, 0 },
	    { "fileorder", '\0', POPT_ARG_STRING, &depOrderFile, 0 },
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

    if (depOrderFile) {
	FILE *f;
	int nalloced = 0;
	int numpkgs = 0;
	int len = 0;
	char b[80];
	char *p;
	int i;
	
	if (!(f = fopen(depOrderFile, "r"))) {
	    fprintf (stderr, "Unable to read %s\n", depOrderFile);
	    usage();
	}
	
	while ((fgets(b, sizeof(b) - 1, f))) {
	    if (numpkgs == nalloced - 1) {
		depOrder = realloc (depOrder, sizeof (char *) * (nalloced += 5));
		memset (depOrder + numpkgs, '\0', 5);
	    }

	    p = b + strlen(b);
	    i = 0;
	    /* trim off two '.' worth of data */
	    while (p > b && i < 2) {
		p--;
		if (*p == '.')
		    i++;
	    }
	    *p = '\0';

	    len = strlen(b);
	    depOrder[numpkgs] = malloc (len + 1);
	    strcpy (depOrder[numpkgs], b);
	    numpkgs++;
	}
    }
    
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

/*      if (args > 1 && !doNumber) { */
/*  	fprintf(stderr, "error: building hdlist for multiple trees without numbers\n"); */
/*  	exit(1); */
/*      } */

    while (args[0]) {
	if (onePass(outfd, args[0], cdNum))
	    return 1;
	if (doNumber) cdNum++;
	args++;
    }

    Fclose(outfd);

    poptFreeContext(optCon);

    qsort(pkgList, pkgListItems, sizeof(*pkgList), pkgInfoCmp);
    rc = 0;
    for (i = 1; i < pkgListItems; i++) {
	if (!pkgInfoCmp(pkgList + i - 1, pkgList + i)) {
	    fprintf(stderr, "duplicate package for %s on %s\n",
		    pkgList[i].name, pkgList[i].arch);
	    rc = 1;
	}
    }

    return rc;
}

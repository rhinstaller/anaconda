#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <rpm/rpmlib.h>
#include <rpm/header.h>
#include <string.h>

#include "hash.h"
#include "upgrade.h"

#define MAXPKGS 1024

#define USEDEBUG 0

#define DEBUG(x) {   \
     if (USEDEBUG)   \
         printf x; \
     }

#if 0
static void printMemStats(char *mess)
{
    char buf[1024];
    printf("%s\n", mess);
    sprintf(buf, "cat /proc/%d/status | grep VmSize", getpid());
    system(buf);
}
#endif

int pkgCompare(void * first, void * second) {
    struct packageInfo ** a = first;
    struct packageInfo ** b = second;

    /* put packages w/o names at the end */
    if (!(*a)->name) return 1;
    if (!(*b)->name) return -1;

    return strcasecmp((*a)->name, (*b)->name);
}


static void compareFileList(int availFileCount, char **availFiles,
			    int installedFileCount, char **installedFiles,
			    struct hash_table *ht)
{
    int installedX, availX, rc;
    
    availX = 0;
    installedX = 0;
    while (installedX < installedFileCount) {
	if (availX == availFileCount) {
	    /* All the rest have moved */
	    DEBUG(("=> %s\n", installedFiles[installedX]));
	    if (strncmp(installedFiles[installedX], "/etc/rc.d/", 10))
		htAddToTable(ht, installedFiles[installedX]);
	    installedX++;
	} else {
	    rc = strcmp(availFiles[availX], installedFiles[installedX]);
	    if (rc > 0) {
		/* Avail > Installed -- file has moved */
		DEBUG (("=> %s\n", installedFiles[installedX]));
		if (strncmp(installedFiles[installedX], "/etc/rc.d/", 10))
		    htAddToTable(ht, installedFiles[installedX]);
		installedX++;
	    } else if (rc < 0) {
		/* Avail < Installed -- avail has some new files */
		availX++;
	    } else {
		/* Files are equal -- file not moved */
		availX++;
		installedX++;
	    }
	}
    }
}

static void addLostFiles(rpmdb db, struct pkgSet *psp, struct hash_table *ht)
{
    int num;
    Header h;
    char *name;
    struct packageInfo **pack;
    struct packageInfo key;
    struct packageInfo *keyaddr = &key;
    char **installedFiles;
    int installedFileCount;

    num = rpmdbFirstRecNum(db);
    while (num) {
	h = rpmdbGetRecord(db, num);
	headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);
	if (name && !strcmp(name, "metroess")) {
	    /* metro was removed from 5.1, but leave it if it's already
	       installed */
	    headerFree(h);
	    num = rpmdbNextRecNum(db, num);
	    continue;
	}
	key.name = name;
	
	pack = bsearch(&keyaddr, psp->packages, psp->numPackages,
		       sizeof(*psp->packages), (void *)pkgCompare);
	if (!pack) {
	    if (headerGetEntry(h, RPMTAG_FILENAMES, NULL,
			  (void **) &installedFiles, &installedFileCount)) {
		compareFileList(0, NULL, installedFileCount,
				installedFiles, ht);
		free(installedFiles);
	    }
	}
	
	headerFree(h);
	num = rpmdbNextRecNum(db, num);
    }
}

static int findPackagesWithObsoletes(rpmdb db, struct pkgSet *psp)
{
    dbiIndexSet matches;
    int rc, count, obsoletesCount;
    struct packageInfo **pip;
    char **obsoletes;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	if ((*pip)->selected) {
	    pip++;
	    continue;
	}

	if (headerGetEntry((*pip)->h, RPMTAG_OBSOLETES, NULL,
		       (void **) &obsoletes, &obsoletesCount)) {
	    while (obsoletesCount--) {
		rc = rpmdbFindPackage(db, obsoletes[obsoletesCount], &matches);
		if (!rc) {
		    if (matches.count) {
			(*pip)->selected = 1;
			dbiFreeIndexRecord(matches);
			break;
		    }

		    dbiFreeIndexRecord(matches);
		}
	    }

	    free(obsoletes);
	}

	pip++;
    }

    return 0;
}

static void errorFunction(void)
{
}

static int findUpgradePackages(rpmdb db, struct pkgSet *psp,
			       struct hash_table *ht)
{
    int skipThis;
    Header h, installedHeader;
    char *name, *version, *release;
    dbiIndexSet matches;
    int rc, i, count;
    char **installedFiles, **availFiles;
    int installedFileCount, availFileCount;
    struct packageInfo **pip;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	h = (*pip)->h;
	name = version = release = NULL;
	headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);
	headerGetEntry(h, RPMTAG_VERSION, NULL, (void **) &version, NULL);
	headerGetEntry(h, RPMTAG_RELEASE, NULL, (void **) &release, NULL);
	if (! (name && version && release)) {
	    /* bum header */
	    /*logMessage("Failed with bad header");*/
	    return(-1);
	}
	
	DEBUG (("Avail: %s-%s-%s\n", name, version, release));
	rc = rpmdbFindPackage(db, name, &matches);

	if (rc == 0) {
	    skipThis = 0;
	    rpmErrorSetCallback(errorFunction);
	    for (i = 0; i < matches.count; i++) {
		installedHeader =
		    rpmdbGetRecord(db, matches.recs[i].recOffset);
		if (rpmVersionCompare(installedHeader, h) >= 0) {
		    /* already have a newer version installed */
		    DEBUG (("Already have newer version\n"))
		    skipThis = 1;
		    headerFree(installedHeader);
		    break;
		}
		headerFree(installedHeader);
	    }
	    rpmErrorSetCallback(NULL);
	    if (! skipThis) {
		DEBUG (("No newer version installed\n"))
	    }
	} else {
	    skipThis = 1;
	    DEBUG (("Not installed\n"))
	}
	
	if (skipThis) {
	    DEBUG (("DO NOT INSTALL\n"))
	} else {
	    DEBUG (("UPGRADE\n"))
	    (*pip)->selected = 1;

	    if (!headerGetEntry(h, RPMTAG_FILENAMES, NULL,
			  (void **) &availFiles, &availFileCount)) {
		availFiles = NULL;
		availFileCount = 0;
	    }

	    for (i = 0; i < matches.count; i++) {
		/* Compare the file lists */
		installedHeader =
		    rpmdbGetRecord(db, matches.recs[i].recOffset);
		if (!headerGetEntry(installedHeader, RPMTAG_FILENAMES, NULL,
			      (void **) &installedFiles,
			      &installedFileCount)) {
		    installedFiles = NULL;
		    installedFileCount = 0;
		}

		compareFileList(availFileCount, availFiles,
				installedFileCount, installedFiles, ht);

		if (installedFiles) {
		    free(installedFiles);
		}
		headerFree(installedHeader);
	    }

	    if (availFiles) {
		free(availFiles);
	    }
	}

	if (rc == 0) {
	    dbiFreeIndexRecord(matches);
	}

	DEBUG (("\n\n"))

	pip++;
    }

    return 0;
}

static int removeMovedFilesAlreadyHandled(struct pkgSet *psp,
					  struct hash_table *ht)
{
    char *name;
    int i, count;
    Header h;
    char **availFiles;
    int availFileCount;
    char *file;
    struct packageInfo **pip;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	h = (*pip)->h;
	if ((*pip)->selected) {
	    name = NULL;
	    headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);

	    if (!headerGetEntry(h, RPMTAG_FILENAMES, NULL,
			  (void **) &availFiles, &availFileCount)) {
		availFiles = NULL;
		availFileCount = 0;
	    }

	    for (i = 0; i < availFileCount; i++) {
		if ((file = htInTable(ht, availFiles[i]))) {
		    *file = '\0';
		    DEBUG (("File already in %s: %s\n", name, availFiles[i]))
		    break;
		}
	    }
	    if (availFiles) {
		free(availFiles);
	    }
	}

	pip++;
    }

    return 0;
}

static int findPackagesWithRelocatedFiles(struct pkgSet *psp,
					  struct hash_table *ht)
{
    char *name;
    int i, count;
    Header h;
    char **availFiles;
    int availFileCount;
    char *file;
    struct packageInfo **pip;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	h = (*pip)->h;
	if (! (*pip)->selected) {
	    name = NULL;
	    headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);

	    availFiles = NULL;
	    availFileCount = 0;
	    if (headerGetEntry(h, RPMTAG_FILENAMES, NULL,
			 (void **) &availFiles, &availFileCount)) {
		for (i = 0; i < availFileCount; i++) {
		    if ((file = htInTable(ht, availFiles[i]))) {
			*file = '\0';
			DEBUG (("Found file in %s: %s\n", name,
				availFiles[i]))
			(*pip)->selected = 1;
			break;
		    }
		}
		free(availFiles);
	    }
	}

	pip++;
    }

    return 0;
}

/*
static void printCount(struct pkgSet *psp)
{
    int i, upgradeCount;
    struct packageInfo *pip;
    
    upgradeCount = 0;
    pip = psp->packages;
    i = psp->numPackages;
    while (i--) {
	if (pip->selected) {
	    upgradeCount++;
	}
	pip++;
    }
    logMessage("marked %d packages for upgrade", upgradeCount);
}
*/

static int unmarkPackagesAlreadyInstalled(rpmdb db, struct pkgSet *psp)
{
    dbiIndexSet matches;
    Header h, installedHeader;
    char *name, *version, *release;
    struct packageInfo **pip;
    int count, rc, i;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	if ((*pip)->selected) {
	    h = (*pip)->h;
	    /* If this package is already installed, don't bother */
	    name = version = release = NULL;
	    headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);
	    headerGetEntry(h, RPMTAG_VERSION, NULL, (void **) &version, NULL);
	    headerGetEntry(h, RPMTAG_RELEASE, NULL, (void **) &release, NULL);
	    if (! (name && version && release)) {
		/* bum header */
		/*logMessage("Failed with bad header");*/
		return(-1);
	    }
	    rc = rpmdbFindPackage(db, name, &matches);
	    if (rc == 0) {
		rpmErrorSetCallback(errorFunction);
		for (i = 0; i < matches.count; i++) {
		    installedHeader =
			rpmdbGetRecord(db, matches.recs[i].recOffset);
		    if (rpmVersionCompare(installedHeader, h) >= 0) {
			/* already have a newer version installed */
			DEBUG (("Already have newer version\n"))
			(*pip)->selected = 0;
			headerFree(installedHeader);
			break;
		    }
		    headerFree(installedHeader);
		}
		rpmErrorSetCallback(NULL);
		dbiFreeIndexRecord(matches);
	    }
	}

	pip++;
    }

    return 0;
}
	    
static void emptyErrorCallback(void) {
}

int ugFindUpgradePackages(struct pkgSet *psp, char *installRoot)
{
    rpmdb db;
    struct hash_table *hashTable;
    rpmErrorCallBackType old;    

    /*logDebugMessage(("ugFindUpgradePackages() ..."));*/

    rpmReadConfigFiles(NULL, NULL);

    rpmSetVerbosity(RPMMESS_FATALERROR);
    old = rpmErrorSetCallback(emptyErrorCallback);

    if (rpmdbOpenForTraversal(installRoot, &db)) {
	/*logMessage("failed opening %s/var/lib/rpm/packages.rpm",
		     installRoot);*/
	return(-1);
    }

    rpmErrorSetCallback(old);
    rpmSetVerbosity(RPMMESS_NORMAL);
    
    hashTable = htNewTable(1103);

    /* For all packages that are installed, if there is no package       */
    /* available by that name, add the package's files to the hash table */
    addLostFiles(db, psp, hashTable);
    /*logDebugMessage(("added lost files"));
    printCount(psp);*/
    
    /* Find packges that are new, and mark them in installThisPackage,  */
    /* updating availPkgs with the count.  Also add files to the hash   */
    /* table that do not exist in the new package - they may have moved */
    if (findUpgradePackages(db, psp, hashTable)) {
	rpmdbClose(db);
	return(-1);
    }
    /*logDebugMessage(("found basic packages to upgrade"));
    printCount(psp);
    hash_stats(hashTable);*/

    /* Remove any files that were added to the hash table that are in */
    /* some other package marked for upgrade.                         */
    removeMovedFilesAlreadyHandled(psp, hashTable);
    /*logDebugMessage(("removed extra files which have moved"));
    printCount(psp);*/

    findPackagesWithRelocatedFiles(psp, hashTable);
    /*logDebugMessage(("found packages with relocated files"));
    printCount(psp);*/

    findPackagesWithObsoletes(db, psp);
    /*logDebugMessage(("found packages that obsolete installed packages"));
    printCount(psp);*/
    
    unmarkPackagesAlreadyInstalled(db, psp);
    /*logDebugMessage(("unmarked packages already installed"));
    printCount(psp);*/
    
    htFreeHashTable(hashTable);
    
    /*printMemStats("Done");*/

    rpmdbClose(db);

    return 0;
}

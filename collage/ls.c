#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <glob.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <sys/types.h>
#include <unistd.h>

#include "idmap.h"
#include "ls.h"

struct fileInfo {
    char * name;
    struct stat sb;
};

static void permsString(int mode, char * perms);
static int statFile(char * dir, char * fn, int flags, struct stat * sbp);
static int implicitListFile(int sock, char * path, 
				char * fn, struct stat * sbp, int flags);
static int nameCmp(const void * a, const void * b);
static int sizeCmp(const void * a, const void * b);
static int mtimeCmp(const void * a, const void * b);
static void multicolumnListing(int sock, struct fileInfo * files, 
				int filesCount, int flags);
static int sendDirContents(int sock, char * path, 
		    char * fn, int flags);

static void permsString(int mode, char * perms) {
    strcpy(perms, "----------");

    if (mode & S_ISVTX) perms[9] = 't';

    if (mode & S_IRUSR) perms[1] = 'r';
    if (mode & S_IWUSR) perms[2] = 'w';
    if (mode & S_IXUSR) perms[3] = 'x';

    if (mode & S_IRGRP) perms[4] = 'r';
    if (mode & S_IWGRP) perms[5] = 'w';
    if (mode & S_IXGRP) perms[6] = 'x';

    if (mode & S_IROTH) perms[7] = 'r';
    if (mode & S_IWOTH) perms[8] = 'w';
    if (mode & S_IXOTH) perms[9] = 'x';

    if (mode & S_ISUID) {
        if (mode & S_IXUSR)
            perms[3] = 's';
        else
            perms[3] = 'S';
    }

    if (mode & S_ISGID) {
        if (mode & S_IXGRP)
            perms[6] = 's';
        else
            perms[6] = 'S';
    }

    if (S_ISDIR(mode))
        perms[0] = 'd';
    else if (S_ISLNK(mode)) {
        perms[0] = 'l';
    }
    else if (S_ISFIFO(mode))
        perms[0] = 'p';
    else if (S_ISSOCK(mode))
        perms[0] = 'l';
    else if (S_ISCHR(mode)) {
        perms[0] = 'c';
    } else if (S_ISBLK(mode)) {
        perms[0] = 'b';
    }
}

static int statFile(char * dir, char * fn, int flags, struct stat * sbp) {
    char * filename;

    if (dir) {
	filename = alloca(strlen(dir) + strlen(fn) + 2);
	sprintf(filename, "%s/%s", dir, fn);
    } else
	filename = fn;

    if (!(flags & SENDDIR_FOLLOWLINKS) || stat(filename, sbp)) {
	if (lstat(filename, sbp)) {
	    return 1;
	}
    }

    return 0;
}

char * fileStatStr(char * dir, char * fn, struct stat * sbp, int flags) {
    char * info;
    char perms[12];
    char sizefield[15];
    char ownerfield[9], groupfield[9];
    char timefield[20] = "";
    char * linkto;
    char * namefield = fn;
    time_t themtime;
    time_t currenttime;
    char * name;
    int thisYear = 0;
    int thisMonth = 0;
    struct tm * tstruct;
    int i;
    char * filename;

    if (!sbp) {
	sbp = alloca(sizeof(*sbp));
	if (statFile(dir, fn, flags, sbp))
	    return NULL;
    }

    permsString(sbp->st_mode, perms);

    currenttime = time(NULL);
    tstruct = localtime(&currenttime);
    thisYear = tstruct->tm_year;
    thisMonth = tstruct->tm_mon;

    name = idSearchByUid(sbp->st_uid);
    if (name)
	sprintf(ownerfield, "%-8s", name);
    else
	sprintf(ownerfield, "%-8d", (int) sbp->st_uid);

    name = idSearchByGid(sbp->st_gid);
    if (name)
	sprintf(groupfield, "%-8s", name);
    else
	sprintf(groupfield, "%-8d", (int) sbp->st_gid);

    if (S_ISLNK(sbp->st_mode)) {
	/* they don't reall want to see "opt -> /usr/opt@" */ 

	linkto = alloca(1024);
	strcpy(linkto, "(link)");

	filename = alloca(strlen(dir) + strlen(fn) + 2);
	sprintf(filename, "%s/%s", dir, fn);

	i = readlink(filename, linkto, 1023);
	if (i < 1) 
	    strcpy(linkto, "(cannot read symlink)");
	else
	    linkto[i] = 0;

        namefield = alloca(strlen(fn) + strlen(linkto) + 10);
        sprintf(namefield, "%s -> %s", fn, linkto);

	sprintf(sizefield, "%d", i);
    } else if (S_ISCHR(sbp->st_mode)) {
        perms[0] = 'c';
        sprintf(sizefield, "%3d, %3d", major(sbp->st_rdev), 
		minor(sbp->st_rdev));
    } else if (S_ISBLK(sbp->st_mode)) {
        perms[0] = 'b';
        sprintf(sizefield, "%3d, %3d", major(sbp->st_rdev), 
		minor(sbp->st_rdev));
    } else  {
	sprintf(sizefield, "%8ld", sbp->st_size);
    }

    /* this is important if sizeof(int_32) ! sizeof(time_t) */
    themtime = sbp->st_mtime;
    tstruct = localtime(&themtime);

    if (tstruct->tm_year == thisYear ||
        ((tstruct->tm_year + 1) == thisYear && tstruct->tm_mon > thisMonth))
        strftime(timefield, sizeof(timefield) - 1, "%b %d %H:%M", tstruct);
    else
        strftime(timefield, sizeof(timefield) - 1, "%b %d  %Y", tstruct);

    info = malloc(strlen(namefield) + strlen(timefield) + 85);

    sprintf(info, "%s %3d %8s %8s %8s %s %s", perms, (int) sbp->st_nlink, 
		ownerfield, groupfield, sizefield, timefield, namefield);

    return info;
}

/* Like listFiles(), but don't explode directories or wildcards */
static int implicitListFile(int sock, char * path, 
				char * fn, struct stat * sbp, int flags) {
    char * info;
    char fileType;

    if (flags & SENDDIR_LONG) {
	info = fileStatStr(path, fn, sbp, flags);
	if (info) {
	    write(sock, info, strlen(info));
	    free(info);
	}
    } else {
	write(sock, fn, strlen(fn));
    }

    if (flags & SENDDIR_FILETYPE) {
	if (S_ISSOCK(sbp->st_mode)) {
	    fileType = '=';
	} else if (S_ISFIFO(sbp->st_mode)) {
	    fileType = '|';
	} else if (S_ISDIR(sbp->st_mode)) {
	    fileType = '/';
	} else if (S_IRWXO & sbp->st_mode) {
	    fileType = '*';
	} else {
	    fileType = '\0';
 	}

	if (fileType) write(sock, &fileType, 1);
    }

    write(sock, "\n", 1);

    return 0;
}

static int nameCmp(const void * a, const void * b) {
    const struct fileInfo * one = a;
    const struct fileInfo * two = b;

    return (strcmp(one->name, two->name));
}

static int sizeCmp(const void * a, const void * b) {
    const struct fileInfo * one = a;
    const struct fileInfo * two = b;

    /* list newer files first */

    if (one->sb.st_size < two->sb.st_size)
	return 1;
    else if (one->sb.st_size > two->sb.st_size)
	return -1;

    return 0;
}

static int mtimeCmp(const void * a, const void * b) {
    const struct fileInfo * one = a;
    const struct fileInfo * two = b;

    if (one->sb.st_mtime < two->sb.st_mtime)
	return -1;
    else if (one->sb.st_mtime > two->sb.st_mtime)
	return 1;

    return 0;
}

static void multicolumnListing(int sock, struct fileInfo * files, 
				int filesCount, int flags) {
    int i, j, k;
    int maxWidth = 0;
    char format[20];
    char * fileType = " ";
    char * buf, * name = NULL;
    int rows, columns;

    if (!filesCount) return;

    for (i = 0; i < filesCount; i++) {
	j = strlen(files[i].name);
	if (j > maxWidth) maxWidth = j;
    }

    maxWidth += 3;
    buf = alloca(maxWidth + 1);

    if (flags & SENDDIR_FILETYPE)
	name = alloca(maxWidth);

    columns = 80 / maxWidth;
    if (columns == 0) columns = 1;

    sprintf(format, "%%-%ds", 80 / columns);
    
    rows = filesCount / columns;
    if (filesCount % columns) rows++;

    for (i = 0; i < rows; i++) {
	j = i;
	while (j < filesCount) {
	    if (flags & SENDDIR_FILETYPE) {
		if (S_ISDIR(files[j].sb.st_mode))
		    fileType = "/";
		else if (S_ISSOCK(files[j].sb.st_mode))
		    fileType = "=";
		else if (S_ISFIFO(files[j].sb.st_mode))
		    fileType = "|";
		else if (S_ISLNK(files[j].sb.st_mode))
		    fileType = "@";
		else
		    fileType = " ";

		strcpy(name, files[j].name);
		strcat(name, fileType);
	    } else
		name = files[j].name;

	    if ((j + rows) < filesCount)
		k = sprintf(buf, format, name);
	    else
		k = sprintf(buf, "%s", name);

	    j += rows;

	    write(sock, buf, k);
	}

	write(sock, "\n", 1);
    }
}

static int sendDirContents(int sock, char * path, char * fn, int flags) {
    struct dirent * ent;
    int start, direction;
    DIR * dir;
    int filesAlloced, filesCount, i;
    struct fileInfo * files, * newfiles;
    int failed = 0;
    int total = 0;
    char buf[20];
    char * fullpath;
    char * subdir;

    filesAlloced = 15;
    filesCount = 0;
    files = malloc(sizeof(*files) * filesAlloced);

    if (fn) {
	fullpath = alloca(strlen(path) + strlen(fn) + 2);
	sprintf(fullpath, "%s/%s", path, fn);
    } else
	fullpath = path;

    dir = opendir(fullpath);

    do {
	errno = 0;
	ent = readdir(dir);
	if (errno) {
	    fprintf(stderr, "Error reading directory entry: %s\n",
			strerror(errno));
	    failed = 1;
	} else if (ent && (*ent->d_name != '.' || (flags & SENDDIR_ALL))) {
	    if (filesCount == filesAlloced) {
		filesAlloced += 15;
		newfiles = realloc(files, sizeof(*files) * filesAlloced);
		files = newfiles;
	    }

	    if (!failed) {
		files[filesCount].name = strdup(ent->d_name);

		if (statFile(fullpath, files[filesCount].name, flags,
			     &files[filesCount].sb)) {
		    fprintf(stderr, "stat of %s failed: %s\n" , 
				files[filesCount].name, strerror(errno));
		    failed = 1;
		} else {
		    total += files[filesCount].sb.st_size /
			     1024;
		}

		filesCount++;
	    }
	}
    } while (ent && !failed);

    closedir(dir);

    if (!failed) {
	if (flags & SENDDIR_SORTMTIME) {
	    qsort(files, filesCount, sizeof(*files), mtimeCmp);
	} else if (flags & SENDDIR_SORTSIZE) {
	    qsort(files, filesCount, sizeof(*files), sizeCmp);
	} else if (!(flags & SENDDIR_SORTNONE)) {
	    qsort(files, filesCount, sizeof(*files), nameCmp);
	}

	if (flags & SENDDIR_SORTREVERSE) {
	    direction = -1;
	    start = filesCount - 1;
	} else {
	    direction = 1;
	    start = 0;
	}

	if (fn) {
	    write(sock, fn, strlen(fn));
	    write(sock, ":\n", 2);
	}
	
	if (flags & SENDDIR_MULTICOLUMN) {
	    multicolumnListing(sock, files, filesCount, flags);
	} else {
	    if (flags & SENDDIR_LONG) {
		i = sprintf(buf, "total %d\n", total);
		write(sock, buf, i);
	    }

	    for (i = start; i >= 0  && i < filesCount; i += direction) {
		implicitListFile(sock, fullpath, files[i].name, 
			     &files[i].sb, flags);
	    }
	}

	if (flags & SENDDIR_RECURSE) {
	    for (i = start; i >= 0  && i < filesCount && !failed; 
		 i += direction) {
		if (S_ISDIR(files[i].sb.st_mode) && 
			strcmp(files[i].name, ".") && 
			strcmp(files[i].name, "..")) {
		    write(sock, "\n", 1);

		    if (fn)  {
			subdir = malloc(strlen(fn) + strlen(files[i].name) + 2);
			sprintf(subdir, "%s/%s", fn, files[i].name);
		    } else {
			subdir = files[i].name;
		    }

		    failed = sendDirContents(sock, path, subdir, flags);

		    if (fn) free(subdir);
		}
	    }
	}
    }

    for (i = 0; i < filesCount; i++) {
	free(files[i].name);
    }
    free(files);

    return failed;
}

/* implements 'ls' */
void listFiles(char * path, char * fn, int flags) {
    struct stat sb;
    int i, rc;
    char * filename, * this;
    int isExplicit = 1;
    glob_t matches;
    int failed = 0;

    if (!fn) {
	fn = ".";
	isExplicit = 0;
    }

    filename = malloc(strlen(fn) + strlen(path) + 2);
    sprintf(filename, "%s/%s", path, fn);
    
    rc = glob(filename, GLOB_NOSORT, NULL, &matches);
    if (rc == GLOB_NOMATCH) {
	fprintf(stderr, "File not found.\n");
	return;
    } 
    free(filename);

    for (i = 0; i < matches.gl_pathc && !failed; i++) {
	this = matches.gl_pathv[i] + strlen(path);

	if (!statFile(path, this, flags, &sb)) {
	    if (S_ISDIR(sb.st_mode) && !(flags & SENDDIR_SIMPLEDIRS)) {
		filename = malloc(strlen(path) + strlen(this) + 2);
		sprintf(filename, "%s/%s", path, this);

		failed = sendDirContents(1, filename, NULL, flags);
		free(filename);
	    } else {
		implicitListFile(1, path, this, &sb, flags);
	    }
	} else {
	    write(1, matches.gl_pathv[i], strlen(matches.gl_pathv[i]));
	    write(1, ": file not found.\n", 18);
	}
    }

    globfree(&matches);
}

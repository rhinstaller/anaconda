/*
 * dirbrowser.c - newt-based directory browser to get a file name
 *
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2004 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <dirent.h>
#include <errno.h>
#include <string.h>
#include <sys/stat.h>

#ifndef STANDALONE
#include "log.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#endif

#ifdef STANDALONE
#define _(x) x

static int simpleStringCmp(const void * a, const void * b) {
    const char * first = *((const char **) a);
    const char * second = *((const char **) b);
 
    return strcmp(first, second);
}
#endif

#if 0
/* sample filter function */
/* return 1 if a dir, 0 if not */
int getOnlyDirs(char * dir, struct dirent *entry) {
    struct stat sb;
    char * fn = alloca(strlen(dir) + strlen(entry->d_name) + 2);

    sprintf(fn, "%s/%s", dir, entry->d_name);
    stat(fn, &sb);

    if (!S_ISDIR(sb.st_mode)) {
        return 1;
    }
    return 0;
}
#endif

#define FSTEP 10

static char ** get_file_list(char * dirname, 
                             int (*filterfunc)(char *, struct dirent *)) {
    DIR * dir;
    struct dirent *entry;
    char ** files;
    int numfiles = FSTEP, i = 0;

    dir = opendir(dirname);
    if (dir == NULL) {
        fprintf(stderr, "error opening %s: %s", dirname, strerror(errno));
        return NULL;
    }

    files = malloc(numfiles * sizeof(char *));

    while ((entry = readdir(dir))) {
        if ((strlen(entry->d_name) == 1) && !strncmp(entry->d_name, ".", 1))
            continue;
        if ((strlen(entry->d_name) == 2) && !strncmp(entry->d_name, "..", 2))
            continue;
        if (filterfunc && filterfunc(dirname, entry))
            continue;

        files[i] = strdup(entry->d_name);
        if (i++ >= (numfiles - 1)) {
            numfiles += FSTEP;
            files = realloc(files, numfiles * sizeof(char *));
        }
    }
    files[i] = NULL;
    closedir(dir);

    qsort(files, i, sizeof(*files), simpleStringCmp);
    return files;
}

/* Browse through a directory structure looking for a file.
 * Returns the full path to the file.
 *
 * Parameters:
 * title: Title for newt dialog window
 * dirname: Directory to use for root of browsing.  NOTE: you cannot go
 *          up above this root.
 * filterfunc: An (optional)  function to filter out files based on whatever 
 *             criteria you want.  Returns 1 if it passes, 0 if not.  
 *             Function should take arguments of the directory name and 
 *             the dirent for the file.
 */
char * newt_select_file(char * title, char * text, char * dirname,
                        int (*filterfunc)(char *, struct dirent *)) {
    char ** files;
    char * fn = NULL;
    int i, done = 0;
    char * topdir = dirname;
    char * dir = malloc(PATH_MAX);
    char * path = NULL;
    newtGrid grid, buttons;
    newtComponent f, tb, listbox, ok, cancel;
    struct stat sb;
    struct newtExitStruct es;

    dir = realpath(dirname, dir);

    do {
        files = get_file_list(dir, filterfunc);

        f = newtForm(NULL, NULL, 0);
        grid = newtCreateGrid(1, 4);

        tb = newtTextboxReflowed(-1, -1, text, 60, 0, 10, 0);

        listbox = newtListbox(12, 65, 10, 
                              NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);

        newtListboxSetWidth(listbox, 55);
        buttons = newtButtonBar(_("OK"), &ok, _("Cancel"), &cancel, NULL);
        newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, tb,
                         0, 0, 0, 1, 0, 0);
        newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, listbox,
                         0, 0, 0, 1, 0, 0);
        newtGridSetField(grid, 0, 3, NEWT_GRID_SUBGRID, buttons,
                         0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);
        
        /* if this isn't our topdir, we want to let them go up a dir */
        if (strcmp(topdir, dir))
            newtListboxAppendEntry(listbox, "../", "..");

        for (i = 0; (files[i] != NULL); i++) {
            if ((files[i] == NULL) || (strlen(files[i]) == 0)) continue;
            path = malloc(strlen(files[i]) + strlen(dir) + 2);
            sprintf(path, "%s/%s", dir, files[i]);
            stat(path, &sb);
            free(path);
            if (S_ISDIR(sb.st_mode)) {
                char *dir = malloc(strlen(files[i]) + 2);
                sprintf(dir, "%s/", files[i]);
                newtListboxAppendEntry(listbox, dir, files[i]);
            } else {
                newtListboxAppendEntry(listbox, files[i], files[i]);
            }
        }

        newtGridWrappedWindow(grid, title);
        newtGridAddComponentsToForm(grid, f, 1);
        newtFormRun(f, &es);

        if (es.reason  == NEWT_EXIT_COMPONENT && es.u.co == cancel) {
            fn = NULL;
            done = -1;
        } else {
            fn = (char *) newtListboxGetCurrent(listbox);
            path = malloc(strlen(fn) + strlen(dir) + 2);
            sprintf(path, "%s/%s", dir, fn);

            stat(path, &sb);
            if (!S_ISDIR(sb.st_mode)) {
                fn = path;
                done = 1;
            } else { 
                dir = realpath(path, dir);
                free(path);
            }
        }

        newtGridFree(grid, 1);
        newtFormDestroy(f);
        newtPopWindow();
    } while (done == 0);

    return fn;
}

#ifdef STANDALONE
int main(int argc, char ** argv) {
    char * foo;

    newtInit();
    newtCls();
      
    foo = newt_select_file("Get File Name", "foo, blah blah blah", 
                           "/etc", NULL);
    newtFinished();
    printf("got %s\n", foo);
    return 0;
}
#endif

/* minifind.h
 * 
 * Copyright (c) 2002 Terra Soft Solutions, Inc.
 * Written by Dan Burcaw <dburcaw@terrasoftsolutions.com>
 * 
 * This software may be freely redistributed under the terms of the GNU
 * library public license.
 *
 * You should have received a copy of the GNU Library Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#ifndef MINIFIND_H
#define MINIFIND_H

#include <stdio.h>
#include <string.h>
#include <dirent.h>
#include <malloc.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

struct pathNode
{
  char *path;
  struct pathNode *next;
};

struct findNode
{
  struct pathNode *result;
  struct pathNode *exclude;
};

void insert_node(struct pathNode *n, char *path);
char *stripLastChar(char *in);
char *minifind(char *dir, char *search, struct findNode *list);

#endif /* MINIFIND_H */

/* minifind.c -- simple find library
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

#include "minifind.h"

// insert a node at head of linked-list
void insert_node(struct pathNode *n, char *path)
{
  	struct pathNode *new = (struct pathNode *) malloc(sizeof(struct pathNode));
  	new->path = path;
  	new->next = n->next;
  	n->next = new;
}

// return input strip less last character
char *stripLastChar(char *in)
{
	char *out = malloc(sizeof(char)*strlen(in));
	snprintf(out, strlen(in) - 1, "%s", in);
	return out; 
}

// do the work
char *minifind(char *dir, char *search, struct findNode *list)
{
  	char *d = NULL;
  	int n;
  	struct dirent **namelist;
  	struct stat buf;
 
  	if (dir[strlen(dir)-1] == '/')
	  	dir = stripLastChar(dir);

	// check is there is an exact filematch to dir
	// when search is not specified
	if (search == NULL)
	{
		if (lstat(dir, &buf) == 0)
			insert_node(list->result, dir);
		return 0;
	}

  	n = scandir(dir, &namelist, 0, alphasort);
  	if (n >= 0)
  	{
      		while (n--)
      		{
          		d = malloc(sizeof(char) * (strlen(dir) \
						+ strlen(namelist[n]->d_name)+1));
          		sprintf(d, "%s/%s", dir, namelist[n]->d_name);	 
			if (strstr(namelist[n]->d_name, search))
		      		insert_node(list->result, d);
      
          		if ((lstat(d, &buf) == 0) && S_ISDIR(buf.st_mode))
          		{
              			if (strcmp(namelist[n]->d_name, ".") && 
                  			strcmp(namelist[n]->d_name, ".."))
	          			d = minifind(d, search, list);
          		}
      			free(namelist[n]);
      		}
  		free(namelist);
  		return d;
  	}
  	return 0;
}

#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

#include "hash.h"

#define CHUNK 1

struct filePath {
    char * dir;
    char * base;
} ;

struct bucket {
    struct filePath * data;
    int allocated;
    int firstFree; /* as in data[firstFree] */
};

struct hash_table {
    int size;
    int entries;
    int overHead;
    struct bucket *bucket;
};

struct hash_table *htNewTable(int size)
{
    struct hash_table *res;
    int i = 0;

    res = malloc(sizeof(struct hash_table));
    res->bucket = malloc(sizeof(struct bucket) * size);
    res->size = size;
    res->entries = 0;
    res->overHead = sizeof(struct bucket) * size + CHUNK * sizeof(char *);

    while (i < size) {
	res->bucket[i].data = malloc(CHUNK * sizeof(*res->bucket[i].data));
	res->bucket[i].allocated = CHUNK;
	res->bucket[i].firstFree = 0;
	i++;
    }
    
    return res;
}

void htFreeHashTable(struct hash_table *ht)
{
    struct bucket * b;
    int item;

    b = ht->bucket;
    while (ht->size--) {
	for (item = 0; item < b->firstFree; item++) {
	    free(b->data[item].dir);
	    free(b->data[item].base);
	}
	free(b->data);
	b++;
    }
    free(ht->bucket);
    free(ht);
}

void htHashStats(struct hash_table *t)
{
    int i = 0;
    int empty = 0;

    while (i < t->size) {
	if (t->bucket[i].firstFree != 0) {
	    /*printf("Bucket %d used %d\n", i, t->bucket[i].firstFree);*/
	} else {
	    empty++;
	}
	i++;
    }

    printf("Total Buckets : %d\n", t->size);
    printf("Empty Buckets : %d\n", empty);
    printf("Total Entries : %d\n", t->entries);
    printf("Total Overhead: %d\n", t->overHead);
    printf("Avergage Depth: %f\n", (double)t->entries / (double)t->size);
}

static unsigned int htHashStrings(const char *s, const char *t)
{
    unsigned int res = 0;

    while (*s)
	res = ((res<<1) + (int)(*(s++)));
    while (*t)
	res = ((res<<1) + (int)(*(t++)));

    return res;
}

/* returns bucket # containing item, or -1 */
static int in_table_aux(struct hash_table *t, int hash, const char * dir, 
			const char * base)
{
    int x;

    x = 0;
    while (x < t->bucket[hash].firstFree) {
	if (! strcmp(t->bucket[hash].data[x].dir, dir) &&
	    ! strcmp(t->bucket[hash].data[x].base, base)) {
	    return x;
	}
	x++;
    }
    
    return -1;
}

int htInTable(struct hash_table *t,  const char * dir, const char * base)
{
    int hash;

    hash = htHashStrings(dir, base) % t->size;

    if (in_table_aux(t, hash, dir, base) == -1)
	return 0;
    return 1;
}

void htAddToTable(struct hash_table *t, const char * dir, const char * base)
{
    static int hash = 1;

    if (!dir || !base)
	return;
    
    hash = htHashStrings(dir, base) % t->size;
    if (in_table_aux(t, hash, dir, base) != -1)
	return;

    if (t->bucket[hash].firstFree == t->bucket[hash].allocated) {
	t->bucket[hash].allocated += CHUNK;
	t->bucket[hash].data =
	    realloc(t->bucket[hash].data,
		    t->bucket[hash].allocated * sizeof(*(t->bucket->data)));
	/*printf("Bucket %d grew to %d\n", hash, t->bucket[hash].allocated);*/
	t->overHead += sizeof(char *) * CHUNK;
    }
    /*printf("In bucket %d, item %d\n", hash, t->bucket[hash].firstFree);*/
    t->bucket[hash].data[t->bucket[hash].firstFree].dir = strdup(dir);
    t->bucket[hash].data[t->bucket[hash].firstFree++].base = strdup(base);
    t->entries++;
}

void htRemoveFromTable(struct hash_table *t, const char * dir, 
		       const char * base) {
    int hash;
    int item;
    int last;

    hash = htHashStrings(dir, base) % t->size;
    if ((item = in_table_aux(t, hash, dir, base)) == -1) {
	return;
    }

    free(t->bucket[hash].data[item].dir);
    free(t->bucket[hash].data[item].base);

    last = --t->bucket[hash].firstFree;
    t->bucket[hash].data[item] = t->bucket[hash].data[last];
}

int htNumEntries(struct hash_table *t) {
    return t->entries;
}

void htIterStart(htIterator * iter) {
    iter->bucket = 0;
    iter->item = -1;
}

int htIterGetNext(struct hash_table * t, htIterator * iter, 
		  const char ** dir, const char ** base) {
    iter->item++;
    
    while (iter->bucket < t->size) {
	if (iter->item < t->bucket[iter->bucket].firstFree) {
	    *dir = t->bucket[iter->bucket].data[iter->item].dir;
	    *base = t->bucket[iter->bucket].data[iter->item].base;

	    return 1;
	}

	iter->item++;
	if (iter->item >= t->bucket[iter->bucket].firstFree) {
	    iter->bucket++;
	    iter->item = 0;
	}
    }

    return 0;
}

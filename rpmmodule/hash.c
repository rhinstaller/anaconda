#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

#include "hash.h"

#define CHUNK 4

struct bucket {
    char **data;
    int allocated;
    int firstFree; /* as in data[firstFree] */
};

struct hash_table {
    int size;
    int entries;
    int totalData;
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
    res->totalData = 0;
    res->entries = 0;
    res->overHead = sizeof(struct bucket) * size + CHUNK * sizeof(char *);

    while (i < size) {
	res->bucket[i].data = malloc(CHUNK * sizeof(char *));
	res->bucket[i].allocated = CHUNK;
	res->bucket[i].firstFree = 0;
	i++;
    }
    
    return res;
}

void htFreeHashTable(struct hash_table *ht)
{
    struct bucket * b;

    b = ht->bucket;
    while (ht->size--) {
	while (b->firstFree) {
	    b->firstFree--;
	    free(b->data[b->firstFree]);
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
    printf("Total Data    : %d\n", t->totalData);
    printf("Total Overhead: %d\n", t->overHead);
    printf("Avergage Depth: %f\n", (double)t->entries / (double)t->size);
}

static unsigned int htHashString(char *s)
{
    unsigned int res = 0;

    while (*s)
	res = ((res<<1) + (int)(*(s++)));

    return res;
}

static char *in_table_aux(struct hash_table *t, int hash, char *s)
{
    int x;

    x = 0;
    while (x < t->bucket[hash].firstFree) {
	if (! strcmp(t->bucket[hash].data[x], s)) {
	    return t->bucket[hash].data[x];
	}
	x++;
    }
    
    return NULL;
}

char *htInTable(struct hash_table *t, char *s)
{
    int hash;

    hash = htHashString(s) % t->size;
    return in_table_aux(t, hash, s);
}

void htAddToTable(struct hash_table *t, char *s)
{
    int hash;

    if (s == NULL)
	return;
    
    hash = htHashString(s) % t->size;
    if (in_table_aux(t, hash, s)) {
	return;
    }

    if (t->bucket[hash].firstFree == t->bucket[hash].allocated) {
	t->bucket[hash].allocated += CHUNK;
	t->bucket[hash].data =
	    realloc(t->bucket[hash].data,
		    t->bucket[hash].allocated * sizeof(char *));
	/*printf("Bucket %d grew to %d\n", hash, t->bucket[hash].allocated);*/
	t->overHead += sizeof(char *) * CHUNK;
    }
    /*printf("In bucket %d, item %d\n", hash, t->bucket[hash].firstFree);*/
    t->bucket[hash].data[t->bucket[hash].firstFree++] = strdup(s);
    t->totalData += strlen(s) + 1;
    t->entries++;
}

int htNumEntries(struct hash_table *t) {
    return t->entries;
}

void htIterStart(htIterator * iter) {
    iter->bucket = 0;
    iter->item = -1;
}

int htIterGetNext(struct hash_table * t, htIterator * iter, char ** s) {
    iter->item++;
    
    while (iter->bucket < t->size) {
	if (iter->item < t->bucket[iter->bucket].firstFree) {
	    *s = t->bucket[iter->bucket].data[iter->item];
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

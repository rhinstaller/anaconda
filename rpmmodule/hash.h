#ifndef H_HASH
#define H_HASH

struct hash_table;
typedef struct hash_table * hashTable;

struct ht_iterator {
    int bucket;
    int item;
};

typedef struct ht_iterator htIterator;

struct hash_table *htNewTable(int size);
void htFreeHashTable(struct hash_table *ht);
char *htInTable(struct hash_table *t, char *s);
void htAddToTable(struct hash_table *t, char *s);
void htPrintHashStats(struct hash_table *t);
int htNumEntries(struct hash_table *t);

/* these use static storage */
void htIterStart(htIterator * iter);
int htIterGetNext(struct hash_table * t, htIterator * iter, char ** s);

#endif

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
int htInTable(struct hash_table *t,  const char * dir, const char * base);
void htAddToTable(struct hash_table *t, const char * dir, const char * base);
void htPrintHashStats(struct hash_table *t);
int htNumEntries(struct hash_table *t);
void htRemoveFromTable(struct hash_table *t, const char * dir, 
		       const char * base);

/* these use static storage */
void htIterStart(htIterator * iter);
int htIterGetNext(struct hash_table * t, htIterator * iter, 
		  const char ** dir, const char ** base);

#endif

/*
 * hash.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

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

#include <grp.h>
#include <pwd.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "idmap.h"

struct idMap_s {
    struct idElement * byId;
    int numEntries;
};

typedef struct idMap_s * idMap;

struct idElement {
    long int id;
    char * name;
};

typedef void * (*iterFn)(void);
typedef int (*infoFn)(void * item, struct idElement * el);

static idMap uidMap = NULL;
static idMap gidMap = NULL;

static int idCmp(const void * a, const void * b) {
    const struct idElement * one = a;
    const struct idElement * two = b;

    if (one->id < two->id)
	return -1;
    else if (one->id > two->id)
	return 1;

    return 0;
}

static idMap readmap(iterFn fn, infoFn info) {
    idMap map;
    int alloced;
    void * res;
    struct idElement * newEntries;

    map = malloc(sizeof(*map));
    if (!map) {
	return NULL;
    }

    alloced = 5;
    map->byId = malloc(sizeof(*map->byId) * alloced);
    if (!map->byId) {
	free(map);
	return NULL;
    }
    map->numEntries = 0;

    while ((res = fn())) {
	if (map->numEntries == alloced) {
	    alloced += 5;
	    newEntries = realloc(map->byId, 
					sizeof(*map->byId) * alloced);
	    if (!newEntries) {
		/* FIXME: this doesn't free the id names */
		free(map->byId);
		free(map);
		return NULL;
	    }

	    map->byId = newEntries;
	}

	if (info(res, map->byId + map->numEntries++)) {
	    /* FIXME: this doesn't free the id names */
	    free(map->byId);
	    free(map);
	    return NULL;
	}
    }

    map->byId = realloc(map->byId, 
				sizeof(*map->byId) * map->numEntries);

    qsort(map->byId, map->numEntries, sizeof(*map->byId), idCmp);

    return map;
}

static int pwInfo(struct passwd * pw, struct idElement * el) {
    el->id = pw->pw_uid;
    el->name = strdup(pw->pw_name);

    return el->name == NULL;
}

static int grInfo(struct group * gr, struct idElement * el) {
    el->id = gr->gr_gid;
    el->name = strdup(gr->gr_name);

    return el->name == NULL;
}

idMap readUIDmap(void) {
    idMap result;

    result = readmap((void *) getpwent, (void *) pwInfo);
    endpwent();

    return result;
}

idMap readGIDmap(void) {
    idMap result;

    result = readmap((void *) getgrent, (void *) grInfo);
    endgrent();

    return result;
}

char * idSearchByUid(long int id) {
    struct idElement el = { id, NULL };
    struct idElement * match;

    match = bsearch(&el, uidMap->byId, uidMap->numEntries, 
		   sizeof(*uidMap->byId), idCmp);

    if (match) return match->name; else return NULL;
}

char * idSearchByGid(long int id) {
    struct idElement el = { id, NULL };
    struct idElement * match;

    match = bsearch(&el, gidMap->byId, gidMap->numEntries, 
		   sizeof(*gidMap->byId), idCmp);

    if (match) return match->name; else return NULL;
}

int idInit(void) {
    if (!(uidMap = readUIDmap())) return 1;
    if (!(gidMap = readGIDmap())) return 1;

    return 0;
}

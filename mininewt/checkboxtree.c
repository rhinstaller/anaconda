#include <slang.h>
#include <stdlib.h>
#include <string.h>

#include "newt.h"
#include "newt_pr.h"

struct items {
    char * text;
    const void *data;
    unsigned char selected;
    struct items *next;
    struct items *prev;
    struct items *branch;
    int flags;
    int depth;
};

struct CheckboxTree {
    newtComponent sb;
    struct items * itemlist;
    struct items ** flatList, ** currItem, ** firstItem;
    int flatCount;
    int flags;
    int sbAdjust;
    int curWidth;
    int userHasSetWidth;
    char * seq;
    char * result;
};

static void ctDraw(newtComponent c);
static void ctDestroy(newtComponent co);
static void ctPlace(newtComponent co, int newLeft, int newTop);
struct eventResult ctEvent(newtComponent co, struct event ev);
static void ctMapped(newtComponent co, int isMapped);
static struct items * findItem(struct items * items, const void * data);
static void buildFlatList(newtComponent co);
static void doBuildFlatList(struct CheckboxTree * ct, struct items * item);
enum countWhat { COUNT_EXPOSED=0, COUNT_SELECTED=1 };
static int countItems(struct items * item, enum countWhat justExposed);
static inline void updateWidth(newtComponent co, struct CheckboxTree * ct,
				int maxField);

static struct componentOps ctOps = {
    ctDraw,
    ctEvent,
    ctDestroy,
    ctPlace,
    ctMapped,
} ;

static inline void updateWidth(newtComponent co, struct CheckboxTree * ct,
				int maxField) {
    ct->curWidth = maxField;
    co->width = ct->curWidth + ct->sbAdjust;

    if (ct->sb)
	ct->sb->left = co->left + co->width - 1;
}

static int countItems(struct items * item, enum countWhat what) {
    int count = 0;

    while (item) {
        if ((!item->branch && item->selected == what) || (what == COUNT_EXPOSED))
	    count++;
	if (item->branch || (what == COUNT_EXPOSED && item->selected))
	    count += countItems(item->branch, what);
	item = item->next;
    }

    return count;
}

static void doBuildFlatList(struct CheckboxTree * ct, struct items * item) {
    while (item) {
    	ct->flatList[ct->flatCount++] = item;
	if (item->branch && item->selected) doBuildFlatList(ct, item->branch);
	item = item->next;
    }
}

static void buildFlatList(newtComponent co) {
    struct CheckboxTree * ct = co->data;

    if (ct->flatList) free(ct->flatList);
    ct->flatCount = countItems(ct->itemlist, COUNT_EXPOSED);

    ct->flatList = malloc(sizeof(*ct->flatList) * (ct->flatCount+1));
    ct->flatCount = 0;
    doBuildFlatList(ct, ct->itemlist);
    ct->flatList[ct->flatCount] = NULL;
}

int newtCheckboxTreeAddItem(newtComponent co, 
			    const char * text, const void * data,
			    int flags, int index, ...) {
    va_list argList;
    int numIndexes;
    int * indexes;
    int i;

    va_start(argList, index);
    numIndexes = 0;
    i = index;
    while (i != NEWT_ARG_LAST) {
	numIndexes++;
	i = va_arg(argList, int);
    }

    va_end(argList);

    indexes = alloca(sizeof(*indexes) * (numIndexes + 1));
    va_start(argList, index);
    numIndexes = 0;
    i = index;
    va_start(argList, index);
    while (i != NEWT_ARG_LAST) {
	indexes[numIndexes++] = i;
	i = va_arg(argList, int);
    }
    va_end(argList);

    indexes[numIndexes++] = NEWT_ARG_LAST;

    return newtCheckboxTreeAddArray(co, text, data, flags, indexes);
}

static int doFindItemPath(struct items * items, void * data, int * path, 
			  int * len) {
    int where = 0;

    while (items) {
	if (items->data == data) {
	    if (path) path[items->depth] = where;
	    if (len) *len = items->depth + 1;
	    return 1;
	}

	if (items->branch && doFindItemPath(items->branch, data, path, len)) {
	    if (path) path[items->depth] = where;
	    return 1;
	}

	items = items->next;
	where++;
    }

    return 0;
}

int * newtCheckboxTreeFindItem(newtComponent co, void * data) {
    int len;
    int * path;
    struct CheckboxTree * ct = co->data;

    if (!doFindItemPath(ct->itemlist, data, NULL, &len)) return NULL;

    path = malloc(sizeof(*path) * (len + 1));
    doFindItemPath(ct->itemlist, data, path, NULL);
    path[len] = NEWT_ARG_LAST;

    return path;
}

int newtCheckboxTreeAddArray(newtComponent co, 
			    const char * text, const void * data,
			    int flags, int * indexes) {
    struct items * curList, * newNode, * item;
    struct items ** listPtr = NULL;
    int i, index, numIndexes;
    struct CheckboxTree * ct = co->data;

    numIndexes = 0;
    while (indexes[numIndexes] != NEWT_ARG_LAST) numIndexes++;

    if (!ct->itemlist) {
	if (numIndexes > 1) return -1;

    	ct->itemlist = malloc(sizeof(*ct->itemlist));
    	item = ct->itemlist;
	item->prev = NULL;
	item->next = NULL;
    } else {
	curList = ct->itemlist;
	listPtr = &ct->itemlist;

	i = 0;
	index = indexes[i];
	while (i < numIndexes) {
	    item = curList;

	    if (index == NEWT_ARG_APPEND) {
	    	item = NULL;
	    } else {
		while (index && item) 
		    item = item->next, index--;
	    }

	    i++;
	    if (i < numIndexes) {
		curList = item->branch;
		listPtr = &item->branch;
		if (!curList && (i + 1 != numIndexes)) return -1;

		index = indexes[i];
	    }
	}

	if (!curList) { 			/* create a new branch */
	    item = malloc(sizeof(*curList->prev));
	    item->next = item->prev = NULL;
	    *listPtr = item;
	} else if (!item) {			/* append to end */
	    item = curList;
	    while (item->next) item = item->next;
	    item->next = malloc(sizeof(*curList->prev));
	    item->next->prev = item;
	    item = item->next;
	    item->next = NULL;
	} else { 
	    newNode = malloc(sizeof(*newNode));
	    newNode->prev = item->prev;
	    newNode->next = item;

	    if (item->prev) item->prev->next = newNode;
	    item->prev = newNode;
	    item = newNode;
	    if (!item->prev) *listPtr = item;
	}
    }
    	
    item->text = strdup(text);
    item->data = data;
    if (flags & NEWT_FLAG_SELECTED) {
    	item->selected = 1;
    } else {
	item->selected = 0;
    }
    item->flags = flags;
    item->branch = NULL;
    item->depth = numIndexes - 1;

    i = 4 + (3 * item->depth);

    if ((ct->userHasSetWidth == 0) && ((strlen(text) + i + ct->sbAdjust) > co->width)) {
	updateWidth(co, ct, strlen(text) + i);
    }

    return 0;
}

static struct items * findItem(struct items * items, const void * data) {
    struct items * i;

    while (items) {
	if (items->data == data) return items;
    	if (items->branch) {
	    i = findItem(items->branch, data);
	    if (i) return i;
	}

	items = items->next;
    }

    return NULL;
}

static void listSelected(struct items * items, int * num, const void ** list, int seqindex) {
    while (items) {
	    if ((seqindex ? items->selected==seqindex : items->selected) && !items->branch)
	    list[(*num)++] = (void *) items->data;
	if (items->branch)
	    listSelected(items->branch, num, list, seqindex);
	items = items->next;
    }
}

void newtCheckboxTreeSetWidth(newtComponent co, int width) {
    struct CheckboxTree * ct = co->data;

    co->width = width;
    ct->curWidth = co->width - ct->sbAdjust;
    ct->userHasSetWidth = 1;
    if (ct->sb) ct->sb->left = co->width + co->left - 1;
    ctDraw(co);
}

const void ** newtCheckboxTreeGetSelection(newtComponent co, int *numitems)
{
    return newtCheckboxTreeGetMultiSelection(co, numitems, 0);
}

const void ** newtCheckboxTreeGetMultiSelection(newtComponent co, int *numitems, char seqnum)
{
    struct CheckboxTree * ct;
    const void **retval;
    int seqindex=0;

    if(!co || !numitems) return NULL;

    ct = co->data;
	
    if (seqnum) {
	    while( ct->seq[seqindex] && ( ct->seq[seqindex] != seqnum )) seqindex++;
    } else {
	    seqindex = 0;
    }

    *numitems = countItems(ct->itemlist, (seqindex ? seqindex : COUNT_SELECTED));
    if (!*numitems) return NULL;
    
    retval = malloc(*numitems * sizeof(void *));
    *numitems = 0;
    listSelected(ct->itemlist, numitems, retval, seqindex);

    return retval;
}

newtComponent newtCheckboxTree(int left, int top, int height, int flags) {
	return newtCheckboxTreeMulti(left, top, height, NULL, flags);
}

newtComponent newtCheckboxTreeMulti(int left, int top, int height, char *seq, int flags) {
    newtComponent co;
    struct CheckboxTree * ct;

    co = malloc(sizeof(*co));
    ct = malloc(sizeof(struct CheckboxTree));
    co->callback = NULL;
    co->data = ct;
    co->ops = &ctOps;
    co->takesFocus = 1;
    co->height = height;
    co->width = 0;
    co->isMapped = 0;
    ct->curWidth = 0;
    ct->userHasSetWidth = 0;
    ct->itemlist = NULL;
    ct->firstItem = NULL;
    ct->currItem = NULL;
    ct->flatList = NULL;

    ct->flags = flags;

    if (seq)
	ct->seq = strdup(seq);
    else
	ct->seq = strdup(" *");
    if (flags & NEWT_FLAG_SCROLL) {
	ct->sb = newtVerticalScrollbar(left, top, height,
				       COLORSET_LISTBOX, COLORSET_ACTLISTBOX);
	ct->sbAdjust = 2;
    } else {
	ct->sb = NULL;
	ct->sbAdjust = 0;
    }
    
    return co;
}

static void ctMapped(newtComponent co, int isMapped) {
    struct CheckboxTree * ct = co->data;

    co->isMapped = isMapped;
    if (ct->sb)
	ct->sb->ops->mapped(ct->sb, isMapped);
}

static void ctPlace(newtComponent co, int newLeft, int newTop) {
    struct CheckboxTree * ct = co->data;

    co->top = newTop;
    co->left = newLeft;

    if (ct->sb)
	ct->sb->ops->place(ct->sb, co->left + co->width - 1, co->top);
}

int ctSetItem(newtComponent co, struct items *item, enum newtFlagsSense sense)
{
    struct CheckboxTree * ct = co->data;
    struct items * currItem;
    struct items * firstItem;
    
    if (!item)
	return 1;
    
    switch(sense) {
	case NEWT_FLAGS_RESET:
	    item->selected = 0;
	    break;
	case NEWT_FLAGS_SET:
	    item->selected = 1;
	    break;
	case NEWT_FLAGS_TOGGLE:
	    if (item->branch)
	      item->selected = !item->selected;
	    else if (!(ct->flags & NEWT_CHECKBOXTREE_UNSELECTABLE)) {
		    item->selected++;
		    if (item->selected==strlen(ct->seq))
		      item->selected = 0;
	    }
	    break;
    }

    if (item->branch) {
    	currItem = *ct->currItem;
	firstItem = *ct->firstItem;

    	buildFlatList(co);

    	ct->currItem = ct->flatList;
	while (*ct->currItem != currItem) ct->currItem++;

    	ct->firstItem = ct->flatList;
    	if (ct->flatCount > co->height) {
		struct items ** last = ct->flatList + ct->flatCount - co->height;
		while (*ct->firstItem != firstItem && ct->firstItem != last)
		    ct->firstItem++;
	}
    }

    return 0;
}

static void ctSetItems(struct items *item, int selected)
{
    for (; item; item = item->next) {
	if (!item->branch)
	    item->selected = selected;
	else
	    ctSetItems(item->branch, selected);
    }
}

static void ctDraw(newtComponent co) {
    struct CheckboxTree * ct = co->data;
    struct items ** item; 
    int i, j;
    char * spaces;
    int currRow;

    if (!co->isMapped) return ;

    if (!ct->firstItem) {
	buildFlatList(co);
	ct->firstItem = ct->currItem = ct->flatList;
    }

    item = ct->firstItem;
    
    i = 0;

    newtTrashScreen();
    
    while (*item && i < co->height) {
	newtGotorc(co->top + i, co->left);
	if (*item == *ct->currItem) {
	    SLsmg_set_color(NEWT_COLORSET_ACTLISTBOX);
	    currRow = co->top + i;
	} else
	    SLsmg_set_color(NEWT_COLORSET_LISTBOX);

	for (j = 0; j < (*item)->depth; j++)
	    SLsmg_write_string("   ");

	if ((*item)->branch) {
	    if ((*item)->selected) 
		SLsmg_write_string("<-> ");
	    else
		SLsmg_write_string("<+> ");
	} else {
	    if (ct->flags & NEWT_CHECKBOXTREE_HIDE_BOX) {
		if ((*item)->selected)
		    SLsmg_set_color(NEWT_COLORSET_ACTLISTBOX);
	        SLsmg_write_string("    ");
	    } else {
	        char tmp[5];
	        snprintf(tmp,5,"[%c] ",ct->seq[(*item)->selected]);
	        SLsmg_write_string(tmp);
	    }
	}

	SLsmg_write_nstring((*item)->text, co->width - 4 - 
					   (3 * (*item)->depth));

	SLsmg_set_color(NEWT_COLORSET_LISTBOX);

	item++;
	i++;
    }

    /* There could be empty lines left (i.e. if the user closes an expanded
       list which is the last thing in the tree, and whose elements are
       displayed at the bottom of the screen */
    if (i < co->height) {
	spaces = alloca(co->width);
	memset(spaces, ' ', co->width);
	SLsmg_set_color(NEWT_COLORSET_LISTBOX);
    }
    while (i < co->height) {
	newtGotorc(co->top + i, co->left);
	SLsmg_write_nstring(spaces, co->width);
	i++;
    }
    
    if(ct->sb) {
	newtScrollbarSet(ct->sb, ct->currItem - ct->flatList, 
			 ct->flatCount - 1);
	ct->sb->ops->draw(ct->sb);
    }

    newtGotorc(currRow, co->left + 1);
}

static void ctDestroy(newtComponent co) {
    struct CheckboxTree * ct = co->data;
    struct items * item, * nextitem;

    nextitem = item = ct->itemlist;

    while (item != NULL) {
	nextitem = item->next;
	free(item->text);
	free(item);
	item = nextitem;
    }

    free(ct->seq);
    free(ct);
    free(co);
}

struct eventResult ctEvent(newtComponent co, struct event ev) {
    struct CheckboxTree * ct = co->data;
    struct eventResult er;
    struct items ** listEnd, ** lastItem;
    int key, selnum = 1;

    er.result = ER_IGNORED;

    if(ev.when == EV_EARLY || ev.when == EV_LATE) {
	return er;
    }

    switch(ev.event) {
    case EV_KEYPRESS:
	key = ev.u.key;
	if (key == (char) key && key != ' ') {
	    for (selnum = 0; ct->seq[selnum]; selnum++)
	    if (key == ct->seq[selnum])
		break;
	    if (!ct->seq[selnum])
		switch (key) {
		case '-': selnum = 0; break;
		case '+':
		case '*': selnum = 1; break;
		}
	    if (ct->seq[selnum])
		key = '*';
	}
	switch(key) {
	case ' ':
	case NEWT_KEY_ENTER:
	    ctSetItem(co, *ct->currItem, NEWT_FLAGS_TOGGLE);
	    er.result = ER_SWALLOWED;
	    if (!(*ct->currItem)->branch || (*ct->currItem)->selected)
		key = NEWT_KEY_DOWN;
	    else
		key = '*';
	    break;
	case '*':
	    if ((*ct->currItem)->branch) {
		ctSetItems((*ct->currItem)->branch, selnum);
		if (!(*ct->currItem)->selected)
		    key = NEWT_KEY_DOWN;
	    } else {
		(*ct->currItem)->selected = selnum;
		key = NEWT_KEY_DOWN;
	    }
	    er.result = ER_SWALLOWED;
	    break;
	}
	switch (key) {
	case '*':
	    ctDraw(co);
	    if(co->callback) co->callback(co, co->callbackData);
	    return er;
	case NEWT_KEY_HOME:
	    ct->currItem = ct->flatList;
	    ct->firstItem = ct->flatList;
	    ctDraw(co);
	    if(co->callback) co->callback(co, co->callbackData);
	    er.result = ER_SWALLOWED;
	    return er;
	case NEWT_KEY_END:
	    ct->currItem = ct->flatList + ct->flatCount - 1;
	    if (ct->flatCount <= co->height)
		ct->firstItem = ct->flatList;
	    else
		ct->firstItem = ct->flatList + ct->flatCount - co->height;
	    ctDraw(co);
	    if(co->callback) co->callback(co, co->callbackData);
	    er.result = ER_SWALLOWED;
	    return er;
	case NEWT_KEY_DOWN:
	    if (ev.u.key != NEWT_KEY_DOWN) {
		if(co->callback) co->callback(co, co->callbackData);
		if (strlen(ct->seq) != 2) {
		    ctDraw(co);
		    return er;
		}
	    }
	    if ((ct->currItem - ct->flatList + 1) < ct->flatCount) {
		ct->currItem++;

		if (ct->currItem - ct->firstItem >= co->height) 
		    ct->firstItem++;

		ctDraw(co);
	    } else if (ev.u.key != NEWT_KEY_DOWN)
	        ctDraw(co);
	    if(co->callback) co->callback(co, co->callbackData);
	    er.result = ER_SWALLOWED;
	    return er;
	case NEWT_KEY_UP:
	    if (ct->currItem != ct->flatList) {
		ct->currItem--;

		if (ct->currItem < ct->firstItem)
		    ct->firstItem = ct->currItem;
		    
		ctDraw(co);
	    }
	    er.result = ER_SWALLOWED;
	    if(co->callback) co->callback(co, co->callbackData);
	    return er;
	case NEWT_KEY_PGUP:
	    if (ct->firstItem - co->height < ct->flatList) {
	    	ct->firstItem = ct->currItem = ct->flatList;
	    } else {
		ct->currItem -= co->height;
		ct->firstItem -= co->height;
	    }

	    ctDraw(co);
	    if(co->callback) co->callback(co, co->callbackData);
	    er.result = ER_SWALLOWED;
	    return er;
	case NEWT_KEY_PGDN:
	    listEnd = ct->flatList + ct->flatCount - 1;
	    lastItem = ct->firstItem + co->height - 1;

	    if (lastItem + co->height > listEnd) {
	    	ct->firstItem = listEnd - co->height + 1;
		ct->currItem = listEnd;
	    } else {
	    	ct->currItem += co->height;
		ct->firstItem += co->height;
	    }

	    ctDraw(co);
	    if(co->callback) co->callback(co, co->callbackData);
	    er.result = ER_SWALLOWED;
	    return er;
	}
	break;

    case EV_FOCUS:
	ctDraw(co);
	er.result = ER_SWALLOWED;
	break;
	
    case EV_UNFOCUS:
	ctDraw(co);
	er.result = ER_SWALLOWED;
	break;
    default:
	break;
    }

    return er;
}

const void * newtCheckboxTreeGetCurrent(newtComponent co) {
    struct CheckboxTree * ct = co->data;

    if (!ct->currItem) return NULL;
    return (*ct->currItem)->data;
}

void newtCheckboxTreeSetEntry(newtComponent co, const void * data, const char * text)
{
    struct CheckboxTree * ct;
    struct items * item;
    int i;

    if (!co) return;
    ct = co->data;
    item = findItem(ct->itemlist, data);
    if (!item) return;

    free(item->text);
    item->text = strdup(text);

    i = 4 + (3 * item->depth);

    if ((ct->userHasSetWidth == 0) && ((strlen(text) + i + ct->sbAdjust) > co->width)) {
	updateWidth(co, ct, strlen(text) + i);
    }

    ctDraw(co);
}

char newtCheckboxTreeGetEntryValue(newtComponent co, const void * data)
{
    struct CheckboxTree * ct;
    struct items * item;

    if (!co) return -1;
    ct = co->data;
    item = findItem(ct->itemlist, data);
    if (!item) return -1;
    if (item->branch)
	return item->selected ? NEWT_CHECKBOXTREE_EXPANDED : NEWT_CHECKBOXTREE_COLLAPSED;
    else
	return ct->seq[item->selected];
}

void newtCheckboxTreeSetEntryValue(newtComponent co, const void * data, char value)
{
    struct CheckboxTree * ct;
    struct items * item;
    int i;

    if (!co) return;
    ct = co->data;
    item = findItem(ct->itemlist, data);
    if (!item || item->branch) return;

    for(i = 0; ct->seq[i]; i++)
	if (value == ct->seq[i])
	    break;

    if (!ct->seq[i]) return;
    item->selected = i;

    ctDraw(co);
}


void newtCheckboxTreeSetCurrent(newtComponent co, void * data) {
    struct CheckboxTree * ct = co->data;
    int * path;
    int i, j, itemsAfter;
    struct items * treeTop, * item;

    path = newtCheckboxTreeFindItem(co, data);
    if (!path) return;

    /* traverse the path and turn on all of the branches to this point */
    for (i = 0, treeTop = ct->itemlist; path[i + 1] != NEWT_ARG_LAST; i++) {
	for (j = 0, item = treeTop; j < path[i]; j++)
	    item = item->next;

	item->selected = 1;
	treeTop = item->branch;
    }

    buildFlatList(co);
	
    item = findItem(ct->itemlist, data);

    i = 0;
    while (ct->flatList[i] != item) i++;

    /* choose the top item */
    j = i - (co->height / 2);

    if ((j + co->height) > ct->flatCount) 
	j = ct->flatCount - co->height;
    
    if (j < 0)
	j = 0;

    ct->firstItem = ct->flatList + j;
    ct->currItem = ct->flatList + i;

    ctDraw(co);
}

#ifndef GETPARTS_H
#define GETPARTS_H

char **getPartitionsList(char * disk);
int lenPartitionsList(char **list);
void freePartitionsList(char **list);

#endif

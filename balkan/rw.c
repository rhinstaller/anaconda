#include "balkan.h"
#include "dos.h"

int balkanReadTable(int fd, struct partitionTable * table) {
    return dospReadTable(fd, table);    
}

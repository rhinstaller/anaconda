#include "balkan.h"
#include "dos.h"

int balkanReadTable(int fd, struct partitionTable * table) {
    int ret;

    /* Try sun labels first: they contain
       both magic (tho 16bit) and checksum.  */
    ret = sunpReadTable(fd, table);
    if (ret != BALKAN_ERROR_BADMAGIC)
	return ret;
    ret = bsdlReadTable(fd, table);
    if (ret != BALKAN_ERROR_BADMAGIC)
	return ret;
	
    return dospReadTable(fd, table);    
}

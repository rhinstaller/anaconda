#ifndef H_MODSTUBS
#define H_MODSTUBS

int ourInsmodCommand(int argc, char ** argv);
int ourRmmodCommand(int argc, char ** argv);
int rmmod(char * modName);
int insmod(char * modName, char * path, char ** args);

#endif

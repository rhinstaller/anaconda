#ifndef H_KBD
#define H_KBD

int chooseKeyboard(char ** keymap, char ** kbdtypep, int flags);
void setKickstartKeyboard(struct knownDevices * kd, 
                          struct loaderData_s * loaderData, int argc, 
                          char ** argv, int * flagsPtr);

#endif

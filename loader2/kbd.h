#ifndef H_KBD
#define H_KBD

int chooseKeyboard(struct loaderData_s * loaderData, char ** kbdtypep);
void setKickstartKeyboard(struct loaderData_s * loaderData, int argc, 
                          char ** argv);

#endif

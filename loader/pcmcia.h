#ifndef H_LOADER_PCMCIA
#define H_LOADER_PCMCIA

/* pcic should point to a space 20 characters long */
int startPcmcia(char * floppyDevice, moduleList modLoaded, moduleDeps modDeps, 
		moduleInfoSet modInfo, char * pcic, int flags);

#endif

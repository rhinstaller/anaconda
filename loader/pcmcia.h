#ifndef H_LOADER_PCMCIA
#define H_LOADER_PCMCIA

int startPcmcia(char * floppyDevice, moduleList modLoaded, moduleDeps modDeps,
		 moduleInfoSet modInfo, int flags);

#endif

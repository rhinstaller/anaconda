#ifndef H_USB
#define H_USB

int usbInitialize(moduleList modLoaded, moduleDeps modDeps,
		  moduleInfoSet modInfo, int flags);
void usbInitializeMouse(moduleList modLoaded, moduleDeps modDeps,
                        moduleInfoSet modInfo, int flags);

#endif



                        09Ayuda para los par metros del Kernel07

ALgunos par metros del kernel pueden ser introducidos en la l¡nea de comandos
y pueden pasarse al kernel en funcionamiento. No existe esta opci¢n para
tarjetas ethernet o dispositivos como CD-ROM.

Para introducir una opci¢n en el kernel, utilice el siguiente formato:
     0flinux <options>07
Si se desea un modo diverso de instalaci¢n, insertelo despu‚s de la
opci¢n(s).

Por ejemplo, para instalar en un sistema de 128MB de RAM utilice el modo
experto (expert) y teclee lo siguiente:
     0flinux mem=128M expert07

Para pasar opciones a los m¢dulos, necesitar  usar el modo experto para
inhabilitar el autochequeo de PCI. Cuando el programa de instalaci¢n
interroga sobre el tipo de dispositivo que necesita una opci¢n o un par metro,
responda a ello, en ese momento ver  un lugar donde poder introducir
los datos.

05[F1-Main] [F2-General] [F3-Expert] [F4-Kernel] [F5-Rescue]07

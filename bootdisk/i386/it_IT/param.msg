

                        09Kernel Parameter Help07

Alcuni parametri del kernel possono essere specificati sulla linea di comando
e sono passati direttamente al kernel. Non e' possibile inserire le opzioni
per le schede di rete e per i CD-ROM.

Per passare un'opzione al kernel, e' necessario usare il seguente formato:
     0flinux <options>07
Se si desidera usare un particolare metodo di installazione, basta
inserirlo dopo le opzioni.
Per esempio, per l'installazione su un sistema con 128MB di RAM in expert
mode, digitate il seguente comando:
     0flinux mem=128M expert07

Per passare le opzioni ai moduli, e' necessario usare l'expert mode e
disabilitare il PCI autoprobing.  Durante l'installazione vi verra' chiesto
di inserire le opzioni o i parametri per i dispositivi hardware presenti nel
vostro sistema. 



05[F1-Main] [F2-General] [F3-Expert] [F4-Kernel] [F5-Rescue]07

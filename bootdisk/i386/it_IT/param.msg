

                        09Parametri del kernel - Help07

Alcuni parametri del kernel possono essere specificati sulla linea di comando
e vengono trasmessi direttamente al kernel. Non e' possibile inserire
le opzioni per dispositivi come le schede ethernet o le unita' CD-ROM.

Per trasmettere un'opzione al kernel, utilizzate il seguente formato:
     0flinux <options>07
Se si desidera usare una diversa modalita' di installazione, inseritela dopo
le opzioni.

For example, to install on a system with 128MB of RAM using expert mode, 
type the following:
     0flinux mem=128M expert07

Per trasmettere le opzioni ai moduli, e' necessario usare la modalita' expert
e disabilitare il rilevamento PCI automatico. Il programma di installazione vi
chiedera' di indicare nell'apposito spazio quale dispositivo necessita 
di un'opzione o il parametro ad esso trasmesso. 



05[F1-Main] [F2-General] [F3-Expert] [F4-Kernel] [F5-Rescue]07


                        09Avvio generale - Help07

Ora e' possibile attivare il processo di instalazione. Nella maggior
parte dei casi, e' sufficiente premere 0f<ENTER>07.
L'installer grafico utilizza il framebuffer a colori 16 bit e una risoluzione
di 800x600. Se l'installer grafico vi crea dei problemi, provate con una 
delle opzioni seguenti:
 - Avviate l'installer con una risoluzione di 640x480, digitando 0flowres <ENTER>07
 - Evitate di utilizzare la modalita' framebuffer digitando 0fnofb <ENTER>07.
 - Provate un'altra risoluzione, aggiungendo 'vga=xxx' in funzione
   dei valori seguenti:
         1024x768x8bpp  -> vga=773        1024x768x16bpp  -> vga=791 
         1280x1024x8bpp -> vga=775        1280x1024x16bpp -> vga=794
Alcune configurazioni hardware potrebbero creare problemi relativi
al riconoscimento automatico dei componenti hardware, effettuato durante
l'installazione. Per risolvere tali problemi, riavviate l'installazione
utilizzando la modalita' expert. Per maggiori informazioni, premete 05<F3>07.
Esistono una serie di parametri che possono essere trasmessi al kernel di
Linux all'avvio del sistema. Per maggiori informazioni, premete 05<F4>07. 



05[F1-Principale] [F2-Generale] [F3-Expert] [F4-Kernel] [F5-Rescue]07

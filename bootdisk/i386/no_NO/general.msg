
                        09Hjelp for generell oppstart07

Du er nå klar til å begynne installasjonsprosessen. I de fleste tilfeller
er den beste måten å sette i gang på bare å trykke 0f<ENTER>07.

Den grafiske installasjonen bruker framebuffer i 16-bit farge og 800x600 
oppløsning. Hvis du har problemer med grafisk installasjon, prøv et av 
følgende alternativer:
    -  Start insallasjonen i 640x480 oppløsning ved å skrive 0flowres <ENTER>07.
    -  Unngå å bruke framebuffer-modus ved å skrive 0fnofb <ENTER>07.
    -  Prøv en annen oppløsning ved å oppgi 'vga=xxx' med disse verdiene:
         1024x768x8bpp  -> vga=773        1024x768x16bpp  -> vga=791 
         1280x1024x8bpp -> vga=775        1280x1024x16bpp -> vga=794

Visse maskinvarekonfigurasjoner kan ha problemer med automatisk gjenkjenning
av maskinvare under installasjonen. Hvis du opplever problemer under
installasjonen, start den på nytt og bruk ekspert-modus. Trykk 05<F3>07 for
mer informasjon om ekspert-modus.

Et antall forskjellige parametere kan videresendes til Linux kjernen ved
oppstart. Trykk 05<F4>07 for mer informasjon. 


05[F1-Hoved] [F2-Generelt] [F3-Ekspert] [F4-Kjerne] [F5-Redning]07


                        09Hjælp for generel opstart07

Du er nu klar til at begynde installationsprocessen. I de fleste tilfælde
er den bedste måde at komme i gang på bare at trykke 0f<ENTER>07.

Den grafiske installation bruger framebuffer i 16-bit farve og 800x600 
opløsning. Hvis du har problemer med grafisk installation, prøv et af 
følgende alternativer:
    -  Start insallationen i 640x480 opløsning ved at skrive 0flowres <ENTER>07.
    -  Undgå at bruge framebuffer-modus ved at skrive 0fnofb <ENTER>07.
    -  Prøv en anden opløsning ved at opgive 'vga=xxx' med disse værdier:
         1024x768x8bpp  -> vga=773        1024x768x16bpp  -> vga=791 
         1280x1024x8bpp -> vga=775        1280x1024x16bpp -> vga=794

Visse maskinelkonfigurationer kan have problemer med automatisk genkenning
af maskinel under installationen. Hvis du oplever problemer under
installationen, start den igen og brug ekspert-modus. Tryk 05<F3>07 for
mere information om ekspert-modus.

Et antal forskellige parametere kan videresendes til Linux kernen ved
opstart. Tryk 05<F4>07 for mere information. 


05[F1-Hoved] [F2-Generelt] [F3-Ekspert] [F4-Kerne] [F5-Redning]07

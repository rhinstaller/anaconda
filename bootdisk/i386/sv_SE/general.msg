
                         09Allmaen uppstartshjaelp07

Du aer nu redo att paaboerja installationsprocessen. I de flesta fall aer det
enklaste saettet att starta att helt enkelt bara trycka 0f<ENTER>07-tangenten.

Det grafiska installationsprogrammet anvaender rambufferten ("framebuffer") med
16-bitars faerg och upploesningen 800x600. Om du har problem med det grafiska
installationsprogrammet kan du prova ett av foeljande alternativ:
    -  Starta installationen i upploesningen 640x480 med 0flowres <ENTER>07.
    -  Undvik att anvaenda framebuffer-laeget genom att ange 0fnofb <ENTER>07.
    -  Prova en annan upploesning genom att laegga till "vga=xxx" enligt
       foeljande vaerden:
         1024x768x8bpp  -> vga=773        1024x768x16bpp  -> vga=791 
         1280x1024x8bpp -> vga=775        1280x1024x16bpp -> vga=794

Vissa haardvarukonfigurationer kan ha problem med den automatiska
haardvarudetekteringen som goers under installationen. Om du har problem med
installationen boer du starta om den och anvaenda expertlaeget. Tryck 05<F3>07 foer
mer information om expertlaeget.

Det finns ett antal parametrar som kan skickas till Linuxkaernan vid uppstart.
Tryck 05<F4>07 foer mer information.

05[F1-Huvud] [F2-Allmaen] [F3-Expert] [F4-Kaerna] [F5-Raeddning]07

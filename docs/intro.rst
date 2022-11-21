Introduction to Anaconda
========================

Anaconda is the installation program used by Fedora, Red Hat Enterprise Linux
and some other distributions.

During installation, a target computer's hardware is identified and configured
and the appropriate file systems for the system's architecture are created.
Finally, anaconda allows the user to install the operating system software on
the target computer. Anaconda can also upgrade existing installations of
earlier versions of the same distribution. After the installation is complete,
you can reboot into your installed system and continue doing customization
using the initial setup program.

Anaconda is a fairly sophisticated installer. It supports installation from
local and remote sources such as CDs and DVDs, images stored on a hard drive,
NFS, HTTP, and FTP. Installation can be scripted with kickstart to provide a
fully unattended installation that can be duplicated on scores of machines. It
can also be run over VNC on headless machines. A variety of advanced storage
devices including LVM, RAID, iSCSI, and multipath are supported from the
partitioning program. Anaconda provides advanced debugging features such as
remote logging, access to the python interactive debugger, and remote saving of
exception dumps.

For more news about Anaconda development and planned features you can follow
`our blog <https://rhinstaller.wordpress.com>`_.

History
-------

(The following was contributed by David Cantrell
<dcantrell@redhat.com> and is probably 80% to 90% accurate.  History
is hard to keep track of, but this is what I can recall being both in
the industry at the time but not at Red Hat.)

So the anaconda code base that we all started with began in 1999 or
so, but it was not the original installer used by Red Hat Linux.  Like
many distributions at the time, the installation process was hand
crafted and consisted of a series of steps executed by a collection of
different programs and tools (shell scripts or Perl scripts or custom
programs and so on).  I have not found the original source for that
installer, but I am still hunting.

OK, so anaconda.  Back in the late 1990s there was a huge push of
money in to Linux companies.  Red Hat itself was founded in 1993 and
by the late 90s was a large company.  SuSE was another big one.  I
worked for a company called Walnut Creek CDROM (ftp.cdrom.com) which
sponsored FreeBSD and Slackware Linux.  Out in Utah in the United
States there was a company called Caldera that made a distribution
called OpenLinux (there's actually a lot more history here, Caldera's
product called Caldera Network Desktop was based on Red Hat Linux and
LST (Linux Support Team) Power Linux was based on Slackware
Linux...LST Power Linux became OpenLinux).

Caldera was founded by former Novell employees and the focus was on
business customers.  Red Hat was still just trying to make a general
purpose system and the industry as a whole tended to view the main
competitor to Linux as Windows.  Caldera was trying to make an
enterprise operating system.  The late 1990s saw the first dedicated
Linux trade shows.  No longer did Linux companies go to COMDEX or
Windows World.  We now had the LinuxWorld Conference and Expo.  And I
was at the first one.  And the second, and third, ... all the way
until LWCE stopped being an event.  Companies were using LWCE to drop
huge product announcements.  Well Caldera had an announcement at one
of these events.

They announced the next version of Caldera OpenLinux and one of its
big features was a graphical installer.  This was huge.  This was the
first Linux distribution to feature a graphical installer program.
They wrote it in C++ (probably?) and it used Qt.  Everyone wanted to
know how they made it work.  Since installing packages took a long
time back then, Caldera even put games in the installer.  You could
play Tetris during installation (side note, Be did that in BeOS too
several years before).

They named their installer "Lizard".  Why?  Well, back in the 90s,
every UI thing tended to emulate the Windows "wizard work flow".  The
series of dialog boxes with Next and Back buttons.  Windows created
that workflow and people felt comfortable with it.  They went with
Lizard as a combination of "Linux wizard".  (side note: this is why
you can sometimes see references to "druids" in old Red Hat
documentation, such as "Disk Druid".  No, it's not a wizard like
Windows, it's a druid!)

Caldera got a lot of patents for the installer, including being able
to play a game during installation which is, incidentally, why we
never did that in anaconda.

OK, so Caldera has made Lizard.  Now Red Hat needed to act.  They
created a new installer project to focus on this graphical installer.
The installer was already in Python at this point, but was not
graphical.  Red Hat started working on this.  They went with the name
"anaconda" because (a) it is written in Python and an anaconda snake
is a type of python and (b) the anaconda snake eats lizards in the
wild.

And that's how we got the name anaconda for the installer.  Caldera
eventually disappeared entirely.  OpenLinux didn't go anywhere.  But
Caldera really tried.  The last thing they did?  They bought SCO and
renamed themselves to SCO and sued IBM for infringing on original Unix
code in Linux.  We all know how that turned out.  :)

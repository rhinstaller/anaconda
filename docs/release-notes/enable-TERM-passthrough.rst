:Type: TUI
:Summary: Pass of the TERM environment variable to tmux

:Description:
    Anaconda is now able to pass the ``TERM`` environment variable from kernel parameters to
    the Anaconda tmux session.

    This could be used for example to pass ``TERM=xterm-256color`` from kernel parameters to
    make Anaconda tmux use colors in the host's terminal. Useful especially for VMs, as
    serial terminal type can't properly be detected there.



:Links:
    - https://github.com/rhinstaller/anaconda/pull/6318

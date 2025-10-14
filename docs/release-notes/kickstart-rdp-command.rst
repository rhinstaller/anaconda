:Type: Core / Kickstart
:Summary: Kickstart support for starting RDP installation

:Description:
    This change adds Kickstart-level support to start a remote graphical installation via RDP.
    Anaconda now parses the new rdp Kickstart command (implemented in pykickstart) and
    configures the installer to accept an incoming RDP connection.

    In addition, Anaconda’s **Runtime** D-Bus module exposes a small API to carry the parsed
    RDP configuration (``enabled``, ``username``, ``password``) to the UI layer so that both
    TUI prompts and GUI startup honor Kickstart-provided values.

    Usage in Kickstart:
    - Enable RDP with optional credentials:
        ``rdp [--username USERNAME] [--password PASSWORD]``
    - If credentials are omitted, the installer will prompt early in startup.

    This complements the existing boot options (``inst.rdp``, ``inst.rdp.username``,
    ``inst.rdp.password``) by allowing fully automated, headless setups using Kickstart alone.

:Links:
    - https://github.com/rhinstaller/anaconda/pull/6512
    - https://issues.redhat.com/browse/INSTALLER-4205

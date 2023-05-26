:Type: Partitioning
:Summary: Respect preferred disk label type provided by blivet (#2092091, #2209760)

:Description:
    In Fedora 37, anaconda was changed to always format disks with GPT
    disk labels, so long as blivet reported that the platform supports
    them at all (even if blivet indicated that MBR labels should be
    preferred). This was intended to implement a plan to prefer GPT
    disk labels on x86_64 BIOS installs, but in fact resulted in GPT
    disk labels also being used in other cases. Now, we go back to
    respecting the preferred disk label type indicated by blivet, by
    default (a corresponding change has been made to blivet to make it
    prefer GPT labels on x86_64 BIOS systems). The inst.disklabel
    option can still be used to force a preference for gpt or mbr if
    desired.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2092091
    - https://bugzilla.redhat.com/show_bug.cgi?id=2209760

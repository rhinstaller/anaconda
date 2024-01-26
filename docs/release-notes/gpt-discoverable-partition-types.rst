:Type: Storage
:Summary: Discoverable GPT partitions

:Description:
    Anaconda now creates discoverable GPT partitions. This means that the partitions use correct
    type UUIDs according to the Discoverable Partitions Specification.

    This behavior can be controlled using the new ``gpt_discoverable_partitions`` configuration
    option in the ``Storage`` section, which defaults to ``True``.

:Links:
    - https://bugzilla.redhat.com/show_bug.cgi?id=2178043
    - https://bugzilla.redhat.com/show_bug.cgi?id=2160074
    - https://github.com/rhinstaller/anaconda/pull/4974
    - https://uapi-group.org/specifications/specs/discoverable_partitions_specification/
    - https://www.freedesktop.org/software/systemd/man/systemd-gpt-auto-generator.html

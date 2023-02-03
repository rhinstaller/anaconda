from functools import total_ordering
import rpm


@total_ordering
class RPMVersion:
    def __init__(self, version_string):
        # TODO do we need to parse epoch? nothing in the tests indicates that
        self._version, _, self._release = version_string.partition('-')

    def __str__(self):
        return f'{self._version}-{self._release}'

    def __repr__(self):
        return f'<RPMVersion({str(self)!r})>'

    def __hash__(self):
        return hash((self._version, self._release))

    def __eq__(self, other):
        if not isinstance(other, RPMVersion):
            return NotImplemented

        return (self._version, self._release) == (other._version, other._release)

    def __lt__(self, other):
        if not isinstance(other, RPMVersion):
            return NotImplemented

        return rpm.labelCompare(('0', self._version, self._release),
                                ('0', other._version, other._release)) == -1

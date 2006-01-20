try:
    import readline
    import rlcompleter
    readline.parse_and_bind("tab: complete")
    del rlcompleter
    del readline

    import os
    import sys
    try:
        os.stat('/mnt/source/RHupdates')
        sys.path.insert(0, '/mnt/source/RHupdates')
    except:
        pass
    del sys
    del os
except:
    pass

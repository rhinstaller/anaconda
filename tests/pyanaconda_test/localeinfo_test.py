import mock

class LocaleinfoTest(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['_isys', 'logging', 'pyanaconda.anaconda_log', 'block'])

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

    def tearDown(self):
        self.tearDownModules()

    def expandLangs_test(self):
        from pyanaconda import localeinfo
        exp = localeinfo.expandLangs("fr_FR.utf8@euro")
        self.assertEqual(exp, ['fr_FR.utf8@euro', 'fr_FR', 'fr@euro', 'fr'])

    def get_test(self):
        from pyanaconda import localeinfo

        fs = mock.DiskIO()
        fs['/lang-table'] = """
Czech	cs	latarcyrheb-sun16	cs_CZ.UTF-8	cz-lat2	Europe/Prague\n
English	en	latarcyrheb-sun16	en_US.UTF-8	us	America/New_York\n
Hebrew	he	none	he_IL.UTF-8	us	Asia/Jerusalem"""
        self.take_over_io(fs, localeinfo)

        info = localeinfo.get("en_US.UTF-8")
        self.assertEqual(
            info,
            {'C': ('English', 'en', 'latarcyrheb-sun16', 'us', 'America/New_York'),
             'cs_CZ.UTF-8': ('Czech', 'cs', 'latarcyrheb-sun16', 'cz-lat2', 'Europe/Prague'),
             'en_US.UTF-8': ('English', 'en', 'latarcyrheb-sun16', 'us', 'America/New_York'),
             'he_IL.UTF-8': ('Hebrew', 'he', 'none', 'us', 'Asia/Jerusalem')})

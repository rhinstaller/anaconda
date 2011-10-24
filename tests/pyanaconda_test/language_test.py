#!/usr/bin/python

import mock

ENVIRON_LANG = 'en_US.utf8'

class LanguageTest(mock.TestCase):

    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])

        # Mock filesystem
        self.fs = mock.DiskIO()

        def fake_os_access(path, _):
            return path == 'lang-names'

        self.fs.open('lang-names', 'w').write(
            "Czech\tCestina\n"
            "English\tEnglish\n"
            "Hebrew\tHebrew")

        import pyanaconda.language
        pyanaconda.language.log = mock.Mock()
        pyanaconda.language.gettext = mock.Mock()
        pyanaconda.language.open = self.fs.open
        pyanaconda.language.os = mock.Mock()
        pyanaconda.language.os.access = fake_os_access
        pyanaconda.language.os.environ = {'LANG': ENVIRON_LANG}
        pyanaconda.language.locale = mock.Mock()
        pyanaconda.language.localeinfo.get = mock.Mock(return_value={
                'C': ('English', 'en', 'latarcyrheb-sun16', 'us', 'America/New_York'),
                'cs_CZ.UTF-8': ('Czech', 'cs', 'latarcyrheb-sun16', 'cz-lat2', 'Europe/Prague'),
                'en_US.UTF-8': ('English', 'en', 'latarcyrheb-sun16', 'us', 'America/New_York'),
                'he_IL.UTF-8': ('Hebrew', 'he', 'none', 'us', 'Asia/Jerusalem')})

    def tearDown(self):
        self.tearDownModules()

    def set_inst_lang_g_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang._setInstLang('cs')
        self.assertEqual(pyanaconda.language.os.environ.get('LANG'), 'cs_CZ.UTF-8')
        self.assertEqual(pyanaconda.language.os.environ.get('LC_NUMERIC'), 'C')
        self.assertTrue(pyanaconda.language.locale.setlocale.called)
        self.assertTrue(isinstance(pyanaconda.language.gettext._translations, dict))

    def set_inst_lang_t_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language('t')
        lang._setInstLang('he')
        self.assertEqual(pyanaconda.language.os.environ.get('LANG'), 'en_US.UTF-8')
        self.assertEqual(pyanaconda.language.os.environ.get('LC_NUMERIC'), 'C')
        self.assertTrue(pyanaconda.language.locale.setlocale.called)
        self.assertTrue(isinstance(pyanaconda.language.gettext._translations, dict))

    def get_inst_lang_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang._getInstLang()
        self.assertEqual(ret, 'en_US.UTF-8')

    def set_get_inst_lang_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang._setInstLang('cs')
        ret = lang._getInstLang()
        self.assertEqual(ret, 'cs_CZ.UTF-8')

    def set_system_lang_1_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang._setSystemLang('cs')
        self.assertEqual(lang.info.get('LANG'), 'cs_CZ.UTF-8')
        self.assertEqual(lang.info.get('SYSFONT', ''), 'latarcyrheb-sun16')

    def set_system_lang_2_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang._setSystemLang('he')
        self.assertEqual(lang.info.get('LANG'), 'he_IL.UTF-8')
        self.assertEqual(lang.info.get('SYSFONT', ''), None)

    def set_system_lang_3_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang._setSystemLang('foo')
        self.assertEqual(lang.info.get('LANG'), 'foo')
        self.assertFalse('SYSFONT' in lang.info)

    def system_lang_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        self.assertEqual(lang.info,
            {'LANG': 'cs_CZ.UTF-8', 'SYSFONT': 'latarcyrheb-sun16'})

    def canon_lang_pass_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        self.assertEqual(lang._canonLang('cs_CZ.UTF-8'), 'cs_CZ.UTF-8')
        self.assertEqual(lang._canonLang('cs'), 'cs_CZ.UTF-8')
        self.assertEqual(lang._canonLang('cs_CZ'), 'cs_CZ.UTF-8')

    def canon_lang_raise_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        self.assertRaises(ValueError, lang._canonLang, 'CZ.UTF-8')
        self.assertRaises(ValueError, lang._canonLang, '')
        self.assertRaises(ValueError, lang._canonLang, 's_CZ')
        self.assertRaises(ValueError, lang._canonLang, 'foo')

    def available_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        self.assertEqual(set(lang.available()), set(['Czech', 'English', 'Hebrew']))

    def dracut_setup_args_default_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.dracutSetupArgs()
        self.assertEqual(ret, set(['LANG=%s' % ENVIRON_LANG]))

    def dracut_setup_args_after_set_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        ret = lang.dracutSetupArgs()
        self.assertEqual(ret, set(['LANG=cs_CZ.UTF-8', 'SYSFONT=latarcyrheb-sun16']))

    def get_current_lang_search_list_default_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getCurrentLangSearchList()
        self.assertEqual(set(ret), set([ENVIRON_LANG, 'en_US', 'en', 'C']))

    def get_current_lang_search_list_after_set_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        ret = lang.getCurrentLangSearchList()
        self.assertEqual(set(ret), set(['cs_CZ.UTF-8', 'cs_CZ', 'cs', 'C']))

    def get_default_keyboard_default_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getDefaultKeyboard()
        self.assertEqual(ret, 'us')

    def get_default_keyboard_after_set_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        ret = lang.getDefaultKeyboard()
        self.assertEqual(ret, 'cz-lat2')

    def get_default_keyboard_with_cs_CZ_locale_test(self):
        import pyanaconda.language
        pyanaconda.language.os.environ = {'LANG': 'cs'}
        lang = pyanaconda.language.Language()
        ret = lang.getDefaultKeyboard()
        self.assertEqual(ret, 'cz-lat2')

    def get_default_time_zone_default_test(self):
        import pyanaconda.language
        pyanaconda.language.os.path.exists = mock.Mock(return_value=False)
        lang = pyanaconda.language.Language()
        ret = lang.getDefaultTimeZone()
        self.assertEqual(ret, 'America/New_York')

    def get_default_time_zone_with_cs_CZ_locale_test(self):
        import pyanaconda.language
        pyanaconda.language.os.environ = {'LANG': 'cs'}
        pyanaconda.language.os.path.exists = mock.Mock(return_value=False)
        lang = pyanaconda.language.Language()
        ret = lang.getDefaultTimeZone()
        self.assertEqual(ret, 'Europe/Prague')

    def get_default_time_zone_after_set_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        ret = lang.getDefaultTimeZone()
        self.assertEqual(ret, 'Europe/Prague')

    def get_text_supported_1_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        self.assertTrue(lang.textSupported('cs'))

    def get_text_supported_2_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        self.assertFalse(lang.textSupported('he'))

    def get_lang_name_1_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getLangName('en')
        self.assertEqual(ret, 'English')

    def get_lang_name_2_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getLangName('cs')
        self.assertEqual(ret, 'Czech')

    def get_lang_name_3_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getLangName('he')
        self.assertEqual(ret, 'Hebrew')

    def get_lang_name_4_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getLangName('foo')
        self.assertEqual(ret, 'English')

    def get_lang_by_name_1_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getLangByName('English')
        self.assertEqual(ret, 'C')

    def get_lang_by_name_2_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getLangByName('Czech')
        self.assertEqual(ret, 'cs_CZ.UTF-8')

    def get_native_lang_name_1_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getNativeLangName('Czech')
        self.assertEqual(ret, 'Cestina')

    def get_native_lang_name_2_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.getNativeLangName('English')
        self.assertEqual(ret, 'English')

    def write_1_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        ret = lang.write()
        self.assertEqual(self.fs['/mnt/sysimage/etc/sysconfig/i18n'], 'LANG="%s"\n' % ENVIRON_LANG)

    def write_2_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        ret = lang.write()
        self.assertEqual(self.fs['/mnt/sysimage/etc/sysconfig/i18n'],
            'LANG="cs_CZ.UTF-8"\nSYSFONT="latarcyrheb-sun16"\n')

    def write_ks_test(self):
        import pyanaconda.language
        lang = pyanaconda.language.Language()
        lang.systemLang = 'cs'
        f = self.fs.open('/tmp/lang', 'w')
        lang.writeKS(f)
        f.close()
        self.assertEqual(self.fs['/tmp/lang'], 'lang cs_CZ.UTF-8\n')


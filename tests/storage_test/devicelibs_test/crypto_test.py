#!/usr/bin/python
import baseclass
import unittest
from mock import acceptance

import tempfile
import os

class CryptoTestCase(baseclass.DevicelibsTestCase):

    def testCrypto(self):
        _LOOP_DEV0 = self._loopMap[self._LOOP_DEVICES[0]]
        _LOOP_DEV1 = self._loopMap[self._LOOP_DEVICES[1]]

        import storage.devicelibs.crypto as crypto


    @acceptance
    def testCrypto(self):
        ##
        ## is_luks
        ##
        # pass
        self.assertEqual(crypto.is_luks(_LOOP_DEV0), -22)
        self.assertEqual(crypto.is_luks("/not/existing/device"), -22)

        ##
        ## luks_format
        ##
        # pass
        self.assertEqual(crypto.luks_format(_LOOP_DEV0, passphrase="secret", cipher="aes-cbc-essiv:sha256", key_size=256), None)

        # make a key file
        handle, keyfile = tempfile.mkstemp(prefix="key", text=False)
        os.write(handle, "nobodyknows")
        os.close(handle)

        # format with key file
        self.assertEqual(crypto.luks_format(_LOOP_DEV1, key_file=keyfile), None)

        # fail
        self.assertRaises(crypto.CryptoError, crypto.luks_format, "/not/existing/device", passphrase="secret", cipher="aes-cbc-essiv:sha256", key_size=256)
        # no passhprase or key file
        self.assertRaises(ValueError, crypto.luks_format, _LOOP_DEV1, cipher="aes-cbc-essiv:sha256", key_size=256)

        ##
        ## is_luks
        ##
        # pass
        self.assertEqual(crypto.is_luks(_LOOP_DEV0), 0)    # 0 = is luks
        self.assertEqual(crypto.is_luks(_LOOP_DEV1), 0)

        ##
        ## luks_add_key
        ##
        # pass
        self.assertEqual(crypto.luks_add_key(_LOOP_DEV0, new_passphrase="another-secret", passphrase="secret"), None)

        # make another key file
        handle, new_keyfile = tempfile.mkstemp(prefix="key", text=False)
        os.write(handle, "area51")
        os.close(handle)

        # add new key file
        self.assertEqual(crypto.luks_add_key(_LOOP_DEV1, new_key_file=new_keyfile, key_file=keyfile), None)

        # fail
        self.assertRaises(crypto.CryptoError, crypto.luks_add_key, _LOOP_DEV0, new_passphrase="another-secret", passphrase="wrong-passphrase")

        ##
        ## luks_remove_key
        ##
        # fail
        self.assertRaises(RuntimeError, crypto.luks_remove_key, _LOOP_DEV0, del_passphrase="another-secret", passphrase="wrong-pasphrase")

        # pass
        self.assertEqual(crypto.luks_remove_key(_LOOP_DEV0, del_passphrase="another-secret", passphrase="secret"), None)

        # remove key file
        self.assertEqual(crypto.luks_remove_key(LOOP_DEV1, del_key_file=new_keyfile, key_file=keyfile), None)

        ##
        ## luks_open
        ##
        # pass
        self.assertEqual(crypto.luks_open(_LOOP_DEV0, "crypted", passphrase="secret"), None)
        self.assertEqual(crypto.luks_open(_LOOP_DEV1, "encrypted", key_file=keyfile), None)

        # fail
        self.assertRaises(crypto.CryptoError, crypto.luks_open, "/not/existing/device", "another-crypted", passphrase="secret")
        self.assertRaises(crypto.CryptoError, crypto.luks_open, "/not/existing/device", "another-crypted", key_file=keyfile)
        # no passhprase or key file
        self.assertRaises(ValueError, crypto.luks_open, _LOOP_DEV1, "another-crypted")

        ##
        ## luks_status
        ##
        # pass
        self.assertEqual(crypto.luks_status("crypted"), True)
        self.assertEqual(crypto.luks_status("encrypted"), True)
        self.assertEqual(crypto.luks_status("another-crypted"), False)

        ##
        ## luks_uuid
        ##
        # pass
        uuid = crypto.luks_uuid(_LOOP_DEV0)
        self.assertEqual(crypto.luks_uuid(_LOOP_DEV0), uuid)
        uuid = crypto.luks_uuid(_LOOP_DEV1)
        self.assertEqual(crypto.luks_uuid(_LOOP_DEV1), uuid)

        ##
        ## luks_close
        ##
        # pass
        self.assertEqual(crypto.luks_close("crypted"), None)
        self.assertEqual(crypto.luks_close("encrypted"), None)

        # fail
        self.assertRaises(crypto.CryptoError, crypto.luks_close, "wrong-name")
        # already closed
        self.assertRaises(crypto.CryptoError, crypto.luks_close, "crypted")
        self.assertRaises(crypto.CryptoError, crypto.luks_close, "encrypted")

        # cleanup
        os.unlink(keyfile)
        os.unlink(new_keyfile)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(CryptoTestCase)


if __name__ == "__main__":
    unittest.main()

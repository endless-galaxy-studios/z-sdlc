"""ed25519.py (the production broker's receipt signatures, z-sdlc process/factory.md D4): signing and the public key
come from OpenSSL 3, whose scalar multiplication is constant-time, and never from the plain-Python code, whose time
depends on the secret's bits. Verifying stays plain Python. Ed25519 is deterministic, so OpenSSL's signatures must
equal RFC 8032's test vectors and the reference signer's, byte for byte, which catches any mistake in the key's
format. Run by CI: python -m unittest discover -s .github/factory/tests"""

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import ed25519  # noqa: E402

# RFC 8032 § 7.1, tests 1 to 3: secret, public, message, signature.
VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe2465"
     "5141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302ae"
     "eb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc"
     "027beceea1ec40a"),
]


class Signing(unittest.TestCase):
    def test_rfc_8032_vectors(self):
        for secret, public, message, signature in VECTORS:
            with self.subTest(public=public[:8]):
                sk, msg = bytes.fromhex(secret), bytes.fromhex(message)
                self.assertEqual(ed25519.public_key(sk).hex(), public)
                if msg:  # test 1's message is empty: OpenSSL 3.0 can't sign one, and a receipt never is
                    self.assertEqual(ed25519.sign(sk, msg).hex(), signature)
                else:
                    with self.assertRaisesRegex(ValueError, "the message is empty"):
                        ed25519.sign(sk, msg)
                self.assertEqual(ed25519._reference_sign(sk, msg).hex(), signature)
                self.assertTrue(ed25519.verify(bytes.fromhex(public), msg, bytes.fromhex(signature)))
                self.assertFalse(ed25519.verify(bytes.fromhex(public), msg + b"x", bytes.fromhex(signature)))

    def test_openssl_and_the_reference_agree(self):
        for size in (1, 64, 1000):
            with self.subTest(size=size):
                sk, msg = os.urandom(32), os.urandom(size)
                self.assertEqual(ed25519.sign(sk, msg), ed25519._reference_sign(sk, msg))
                self.assertEqual(ed25519.public_key(sk), ed25519._reference_public_key(sk))

    def test_the_secret_never_reaches_the_plain_python_code(self):
        # _expand turns the secret into the scalar the plain-Python code multiplies by: a signer that used it would
        # fail here, as the reference signer does.
        sk = os.urandom(32)
        with mock.patch.object(ed25519, "_expand", side_effect=AssertionError("the secret reached plain Python")):
            sig = ed25519.sign(sk, b"receipt")
            pub = ed25519.public_key(sk)
            with self.assertRaises(AssertionError):
                ed25519._reference_sign(sk, b"receipt")
        self.assertTrue(ed25519.verify(pub, b"receipt", sig))

    def test_the_secret_is_never_written_to_a_file(self):
        sk, written = os.urandom(32), []
        real = tempfile.NamedTemporaryFile

        def recording(*args, **kwargs):
            f = real(*args, **kwargs)
            write = f.write
            f.write = lambda data: (written.append(bytes(data)), write(data))[1]
            return f
        with mock.patch.object(ed25519.tempfile, "NamedTemporaryFile", recording):
            ed25519.sign(sk, b"receipt")
        self.assertTrue(written)  # the message's file
        self.assertFalse([w for w in written if sk in w])

    def test_without_openssl_3_nothing_is_signed(self):
        with mock.patch.object(ed25519, "_openssls", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "no OpenSSL 3 to sign with in constant time"):
                ed25519.sign(os.urandom(32), b"receipt")
        with tempfile.TemporaryDirectory() as tmp:
            fake = pathlib.Path(tmp) / "openssl"  # LibreSSL's answer to -rawin
            fake.write_text("#!/bin/sh\necho \"unknown option '-rawin'\" >&2\nexit 1\n")
            fake.chmod(0o755)
            with mock.patch.object(ed25519, "_openssls", return_value=[str(fake)]):
                with self.assertRaisesRegex(RuntimeError, "unknown option '-rawin'"):
                    ed25519.sign(os.urandom(32), b"receipt")

    def test_a_signature_from_another_key_is_refused(self):
        # A key-format mistake would sign with some other key: the self-check refuses it.
        other = ed25519._reference_sign(os.urandom(32), b"receipt")
        with mock.patch.object(ed25519, "_openssl", side_effect=[other, ed25519._SPKI + ed25519.public_key(bytes(32))]):
            with self.assertRaisesRegex(RuntimeError, "doesn't verify"):
                ed25519.sign(bytes(32), b"receipt")

    def test_a_secret_is_32_bytes(self):
        with self.assertRaises(ValueError):
            ed25519.sign(b"short", b"receipt")


if __name__ == "__main__":
    unittest.main()

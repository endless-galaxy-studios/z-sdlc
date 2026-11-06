"""Ed25519 signatures (RFC 8032 § 5.1) for the production broker's receipts.

The broker signs each gate result with a root-only key on the host; the hosted report job and the
continuing execution verify it with the public key committed at production/receipt.pub.

Verifying is plain Python, so it runs on the host, on GitHub's runners and in the tests with nothing to
install: it handles only public values. Signing, and deriving the public key, handle the secret, and an
unprivileged user on the host can make the broker sign (a refusal is signed too), so they never run the
plain-Python scalar multiplication, whose time depends on the secret's bits: they run OpenSSL 3's, which is
constant-time, with the key on a pipe and never in a file. A host without OpenSSL 3 fails loudly rather than
sign another way. The plain-Python signer stays, as _reference_sign, for the tests to check OpenSSL's
signatures against (Ed25519 is deterministic: the same key and message give the same bytes).
"""

import hashlib
import os
import shutil
import subprocess
import tempfile

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, P - 2, P) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)


def _sha512(data):
    return hashlib.sha512(data).digest()


def _inv(x):
    return pow(x, P - 2, P)


# Points in extended coordinates (X, Y, Z, T), x = X/Z, y = Y/Z, x*y = T/Z.
def _add(p, q):
    a = (p[1] - p[0]) * (q[1] - q[0]) % P
    b = (p[1] + p[0]) * (q[1] + q[0]) % P
    c = 2 * p[3] * q[3] * D % P
    d = 2 * p[2] * q[2] % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _mul(s, p):
    q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _equal(p, q):
    return (p[0] * q[2] - q[0] * p[2]) % P == 0 and (p[1] * q[2] - q[1] * p[2]) % P == 0


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(D * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_GY = 4 * _inv(5) % P
_GX = _recover_x(_GY, 0)
G = (_GX, _GY, 1, _GX * _GY % P)


def _compress(p):
    zinv = _inv(p[2])
    x, y = p[0] * zinv % P, p[1] * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % P)


def _expand(secret):
    if len(secret) != 32:
        raise ValueError("an Ed25519 secret key is 32 bytes")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def _reference_public_key(secret):
    """The RFC's reference derivation. Not constant-time: the tests' check, never the broker's signer."""
    a, _ = _expand(secret)
    return _compress(_mul(a, G))


def _reference_sign(secret, message):
    """The RFC's reference signer. Not constant-time: the tests' check, never the broker's signer."""
    a, prefix = _expand(secret)
    pub = _compress(_mul(a, G))
    r = int.from_bytes(_sha512(prefix + message), "little") % L
    rs = _compress(_mul(r, G))
    h = int.from_bytes(_sha512(rs + pub + message), "little") % L
    return rs + int.to_bytes((r + h * a) % L, 32, "little")


# A 32-byte Ed25519 secret as PKCS #8 DER, and the SubjectPublicKeyInfo DER a public key comes back in (RFC 8410).
_PKCS8 = bytes.fromhex("302e020100300506032b657004220420")
_SPKI = bytes.fromhex("302a300506032b6570032100")


def _openssls():
    """The openssl programs to try, in order: PATH's, then the usual places (one may be LibreSSL, which can't)."""
    found = []
    for exe in (shutil.which("openssl"), "/usr/bin/openssl", "/usr/local/bin/openssl", "/opt/homebrew/bin/openssl"):
        if exe and exe not in found and os.path.isfile(exe) and os.access(exe, os.X_OK):
            found.append(exe)
    return found


def _openssl(secret, args, data):
    """Run openssl with the secret key as DER on a pipe it reads as /dev/fd/<n> ({key} in args), and the data
    (public: the receipt) in a file of its own ({data}), since a one-shot signature needs its input's size:
    stdout of the first openssl that can, or RuntimeError."""
    if not isinstance(secret, (bytes, bytearray)) or len(secret) != 32:
        raise ValueError("an Ed25519 secret key is 32 bytes")
    tried = []
    with tempfile.NamedTemporaryFile() as f:
        f.write(data)
        f.flush()
        for exe in _openssls():
            r, w = os.pipe()
            try:
                os.write(w, _PKCS8 + bytes(secret))
                os.close(w)
                w = None
                p = subprocess.run([exe, *(a.replace("{key}", f"/dev/fd/{r}").replace("{data}", f.name) for a in args)],
                                   stdin=subprocess.DEVNULL, capture_output=True, pass_fds=(r,), timeout=30)
            finally:
                os.close(r)
                if w is not None:
                    os.close(w)
            if p.returncode == 0 and p.stdout:
                return p.stdout
            tried.append(f"{exe}: {(p.stderr.decode(errors='replace').strip().splitlines() or ['exit %d' % p.returncode])[0]}")
    raise RuntimeError("no OpenSSL 3 to sign with in constant time (" + ("; ".join(tried) or "no openssl found")
                       + "): install OpenSSL 3 (Debian and Ubuntu: the openssl package)")


def public_key(secret):
    out = _openssl(secret, ["pkey", "-inform", "DER", "-in", "{key}", "-pubout", "-outform", "DER"], b"")
    if len(out) != 44 or not out.startswith(_SPKI):
        raise RuntimeError("openssl returned no Ed25519 public key")
    return out[12:]


def sign(secret, message):
    # OpenSSL 3.0 to 3.5 can't sign an empty message one-shot ("Could not allocate 0 bytes"); a receipt never is one.
    if not message:
        raise ValueError("sign: the message is empty (a receipt never is)")
    sig = _openssl(secret, ["pkeyutl", "-sign", "-rawin", "-keyform", "DER", "-inkey", "{key}", "-in", "{data}"],
                  bytes(message))
    # A key-format mistake would sign with another key: the signature must verify under this key's public half.
    if len(sig) != 64 or not verify(public_key(secret), bytes(message), sig):
        raise RuntimeError("openssl's signature doesn't verify under the key's public half")
    return sig


def verify(public, message, signature):
    if len(public) != 32 or len(signature) != 64:
        return False
    a = _decompress(public)
    r = _decompress(signature[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= L:
        return False
    h = int.from_bytes(_sha512(signature[:32] + public + message), "little") % L
    return _equal(_mul(s, G), _add(r, _mul(h, a)))

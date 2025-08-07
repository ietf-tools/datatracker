#!/usr/bin/env python
import sys
from base64 import b64decode
from base64 import b64encode
from typing import Dict
from typing import Union
from typing import cast

from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Cipher._mode_ccm import CcmMode
from Cryptodome.Cipher._mode_eax import EaxMode
from Cryptodome.Cipher._mode_gcm import GcmMode
from Cryptodome.Cipher._mode_ocb import OcbMode
from Cryptodome.Cipher._mode_siv import SivMode

from oic.utils import tobytes

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

__author__ = "rolandh"

POSTFIX_MODE: Dict[str, Union[Literal[2], Literal[3]]] = {
    "cbc": AES.MODE_CBC,
    "cfb": AES.MODE_CFB,
    "ecb": AES.MODE_CFB,
}

BLOCK_SIZE = 16


class AESError(Exception):
    pass


def build_cipher(key, iv, alg="aes_128_cbc"):
    """
    Create cipher.

    :param key: encryption key
    :param iv: init vector
    :param alg: cipher algorithm
    :return: A Cipher instance
    """
    _, bits, cmode = alg.split("_")

    if not iv:
        iv = Random.new().read(AES.block_size)
    else:
        if len(iv) != AES.block_size:
            raise AESError("IV must have the AES block size of %d" % AES.block_size)

    if bits not in ["128", "192", "256"]:
        raise AESError("Unsupported key length")
    if len(key) != int(bits) >> 3:
        raise AESError("Wrong Key length")

    try:
        return AES.new(tobytes(key), POSTFIX_MODE[cmode], tobytes(iv)), iv
    except KeyError:
        raise AESError("Unsupported chaining mode")


def encrypt(
    key,
    msg,
    iv=None,
    alg="aes_128_cbc",
    padding="PKCS#7",
    b64enc=True,
    block_size=BLOCK_SIZE,
):
    """
    Encrypt message.

    :param key: The encryption key
    :param iv: init vector
    :param msg: Message to be encrypted
    :param padding: Which padding that should be used
    :param b64enc: Whether the result should be base64encoded
    :param block_size: If PKCS#7 padding which block size to use
    :return: The encrypted message
    """
    if padding == "PKCS#7":
        _block_size = block_size
    elif padding == "PKCS#5":
        _block_size = 8
    else:
        _block_size = 0

    if _block_size:
        plen = _block_size - (len(msg) % _block_size)
        c = chr(plen)
        msg += c * plen

    cipher, iv = build_cipher(tobytes(key), iv, alg)
    cmsg = iv + cipher.encrypt(tobytes(msg))
    if b64enc:
        return b64encode(cmsg)
    else:
        return cmsg


def decrypt(key, msg, iv=None, padding="PKCS#7", b64dec=True):
    """
    Decrypt the message.

    :param key: The encryption key
    :param iv: init vector
    :param msg: Base64 encoded message to be decrypted
    :return: The decrypted message
    """
    if b64dec:
        data = b64decode(msg)
    else:
        data = msg

    cipher, iv = build_cipher(key, iv)
    res = cipher.decrypt(data)[AES.block_size :]
    if padding in ["PKCS#5", "PKCS#7"]:
        res = res[: -res[-1]]
    return res.decode("utf-8")


class AEAD(object):
    """
    Authenticated Encryption with Associated Data Wrapper.

    This does encryption and integrity check in one
    operation, so you do not need to combine HMAC + encryption
    yourself.

    :param key: The key to use for encryption.
    :type key: bytes
    :param iv: The initialization vector.
    :type iv: bytes
    :param mode: One of the AEAD available modes.

    Your key and initialization vectors should be created from random bytes
    of sufficient length.

    For the default SIV mode, you need one of:

        - 256-bit key, 128-bit IV to use AES-128
        - 384-bit key, 192-bit IV to use AES-192
        - 512-bit key, 256-bit IV to use AES-256

    """

    def __init__(self, key, iv, mode=AES.MODE_SIV):
        assert isinstance(key, bytes)  # nosec
        assert isinstance(iv, bytes)  # nosec
        self.key = key
        # The code is written in such a way, that only these modes are actually supported
        # The other ones are missing `encrypt_and_digest`, `decrypt_and_verify` and `update` methods
        assert mode in (  # nosec
            AES.MODE_CCM,
            AES.MODE_EAX,
            AES.MODE_GCM,
            AES.MODE_SIV,
            AES.MODE_OCB,
        )
        self.mode = mode
        self.iv = iv
        self.kernel = cast(
            Union[CcmMode, EaxMode, GcmMode, SivMode, OcbMode],
            AES.new(self.key, self.mode, self.iv),
        )

    def add_associated_data(self, data):
        """
        Add data to include in the MAC.

        This data is protected by the MAC but not encrypted.

        :param data: data to add in the MAC calculation
        :type data: bytes
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.kernel.update(data)

    def encrypt_and_tag(self, cleardata):
        """
        Encrypt the given data.

        Encrypts the given data and returns the encrypted
        data and the MAC to later verify and decrypt the data.

        :param cleardata: data to encrypt
        :type cleardata: bytes

        :returns: 2-tuple of encrypted data and MAC
        """
        assert isinstance(cleardata, bytes)  # nosec
        return self.kernel.encrypt_and_digest(cleardata)

    def decrypt_and_verify(self, cipherdata, tag):
        """
        Decrypt and verify.

        Checks the integrity against the tag and decrypts the
        data. Any associated data used during encryption
        needs to be added before calling this too.

        :param cipherdata: The encrypted data
        :type cipherdata: bytes
        :param tag: The MAC tag
        :type tag: bytes
        """
        assert isinstance(cipherdata, bytes)  # nosec
        assert isinstance(tag, bytes)  # nosec
        try:
            return self.kernel.decrypt_and_verify(cipherdata, tag)
        except ValueError:
            raise AESError("Failed to verify data")

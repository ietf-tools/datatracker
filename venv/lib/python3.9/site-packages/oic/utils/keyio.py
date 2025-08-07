import builtins
import copy
import json
import logging
import os
import sys
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from urllib.parse import urlsplit

import requests
from Cryptodome.PublicKey import RSA
from jwkest import as_bytes
from jwkest import as_unicode
from jwkest import b64e
from jwkest import jwe
from jwkest import jws
from jwkest.ecc import NISTEllipticCurve
from jwkest.jwk import ECKey
from jwkest.jwk import JWKException
from jwkest.jwk import RSAKey
from jwkest.jwk import SYMKey
from jwkest.jwk import rsa_load

from oic.exception import MessageException
from oic.exception import PyoidcError

__author__ = "rohe0002"

KEYLOADERR = "Failed to load %s key from '%s' (%s)"
REMOTE_FAILED = "Remote key update from '{}' failed, HTTP status {}"
MALFORMED = "Remote key update from {} failed, malformed JWKS."

logger = logging.getLogger(__name__)


def raise_exception(excep, descr, error="service_error"):
    _err = json.dumps({"error": error, "error_description": descr})
    raise excep(_err, "application/json")


class KeyIOError(PyoidcError):
    pass


class UnknownKeyType(KeyIOError):
    pass


class UpdateFailed(KeyIOError):
    pass


class JWKSError(KeyIOError):
    pass


K2C = {"RSA": RSAKey, "EC": ECKey, "oct": SYMKey}
KEYS = Union[RSAKey, SYMKey, ECKey]


class KeyBundle(object):
    def __init__(
        self,
        keys=None,
        source="",
        cache_time=300,
        verify_ssl=True,
        fileformat="jwk",
        keytype="RSA",
        keyusage=None,
        timeout=5,
    ):
        """
        Initialize the KeyBundle.

        :param keys: A list of dictionaries
            with the keys ["kty", "key", "alg", "use", "kid"]
        :param source: Where the key set can be fetch from
        :param verify_ssl: Verify the SSL cert used by the server
        :param fileformat: For a local file either "jwk" or "der"
        :param keytype: Iff local file and 'der' format what kind of key it is.
        :param timeout: Timeout for requests library. Can be specified either as
            a single integer or as a tuple of integers. For more details, refer to
            ``requests`` documentation.
        """
        self._keys: List[KEYS] = []
        self.remote = False
        self.verify_ssl = verify_ssl
        self.cache_time = cache_time
        self.time_out = 0
        self.etag = ""
        self.source: Optional[str] = None
        self.fileformat = fileformat.lower()
        self.keytype = keytype
        self.keyusage = keyusage
        self.imp_jwks: Dict[str, Any] = {}
        self.last_updated: float = 0
        self.timeout = timeout

        if keys:
            self.source = None
            if isinstance(keys, dict):
                self.do_keys([keys])
            else:
                self.do_keys(keys)
        else:
            if source.startswith("file://"):
                self.source = source[7:]
            elif source.startswith("http://") or source.startswith("https://"):
                self.source = source
                self.remote = True
            elif source == "":
                return
            else:
                raise KeyIOError("Unsupported source type: %s" % source)

            if not self.remote:  # local file
                if self.fileformat == "jwk":
                    self.do_local_jwk(self.source)
                elif self.fileformat == "der":  # Only valid for RSA keys
                    self.do_local_der(self.source, self.keytype, self.keyusage)

    def do_keys(self, keys):
        """
        Go from JWK description to binary keys.

        :param keys:
        :return:
        """
        for inst in keys:
            if not isinstance(inst, dict):
                raise JWKSError("Illegal JWK")

            typ = inst["kty"]
            flag = 0
            for _typ in [typ, typ.lower(), typ.upper()]:
                try:
                    _key = K2C[_typ](**inst)
                except KeyError:
                    continue
                except TypeError:
                    raise JWKSError("Inappropriate JWKS argument type")
                except JWKException as err:
                    logger.warning("Loading a key failed: %s", err)
                else:
                    if _key not in self._keys:
                        self._keys.append(_key)
                        flag = 1
                        break
            if not flag:
                logger.warning("Unknown key type: %s", typ)

    def do_local_jwk(self, filename):
        try:
            with open(filename) as f:
                self.do_keys(json.loads(f.read())["keys"])
        except KeyError:
            logger.error("Now 'keys' keyword in JWKS")
            raise_exception(
                UpdateFailed, "Local key update from '{}' failed.".format(filename)
            )
        else:
            self.last_updated = time.time()

    def do_local_der(self, filename, keytype, keyusage):
        # This is only for RSA keys
        _bkey = rsa_load(filename)

        if not keyusage:
            keyusage = ["enc", "sig"]

        for use in keyusage:
            _key = RSAKey().load_key(_bkey)
            _key.use = use
            self._keys.append(_key)

        self.last_updated = time.time()

    def do_remote(self):
        if self.source is None:
            # Nothing to do
            return False
        args = {"verify": self.verify_ssl}
        if self.etag:
            args["headers"] = {"If-None-Match": self.etag}

        try:
            logger.debug("KeyBundle fetch keys from: %s", self.source)
            r = requests.get(self.source, timeout=self.timeout, **args)
        except Exception as err:
            logger.error("%s", err)
            raise_exception(UpdateFailed, REMOTE_FAILED.format(self.source, str(err)))

        if r.status_code == 304:  # file has not changed
            self.time_out = time.time() + self.cache_time
            self.last_updated = time.time()
            try:
                self.do_keys(self.imp_jwks["keys"])
            except KeyError:
                logger.error("No 'keys' keyword in JWKS")
                raise_exception(UpdateFailed, "No 'keys' keyword in JWKS")
            else:
                return False
        elif r.status_code == 200:  # New content
            self.time_out = time.time() + self.cache_time

            self.imp_jwks = self._parse_remote_response(r)
            if not isinstance(self.imp_jwks, dict) or "keys" not in self.imp_jwks:
                raise_exception(UpdateFailed, MALFORMED.format(self.source))

            logger.debug("Loaded JWKS: %s from %s" % (r.text, self.source))
            try:
                self.do_keys(self.imp_jwks["keys"])
            except KeyError:
                logger.error("No 'keys' keyword in JWKS")
                raise_exception(UpdateFailed, MALFORMED.format(self.source))

            try:
                self.etag = r.headers["Etag"]
            except KeyError:
                pass
        else:
            raise_exception(
                UpdateFailed, REMOTE_FAILED.format(self.source, r.status_code)
            )
        self.last_updated = time.time()
        return True

    def _parse_remote_response(self, response):
        """
        Parse JWKS from the HTTP response.

        Should be overridden by subclasses for adding support of e.g. signed
        JWKS.
        :param response: HTTP response from the 'jwks_uri' endpoint
        :return: response parsed as JSON
        """
        # Check if the content type is the right one.
        try:
            if (
                not response.headers["Content-Type"]
                .lower()
                .startswith("application/json")
            ):
                logger.warning("Wrong Content_type")
        except KeyError:
            pass

        logger.debug("Loaded JWKS: %s from %s" % (response.text, self.source))
        try:
            return json.loads(response.text)
        except ValueError:
            return None

    def _uptodate(self):
        res = False
        if self._keys is not []:
            if self.remote:  # verify that it's not to old
                if time.time() > self.time_out:
                    if self.update():
                        res = True
        elif self.remote:
            if self.update():
                res = True
        return res

    def update(self):
        """
        Reload the key if necessary.

        This is a forced update, will happen even if cache time has not elapsed.
        """
        res = True  # An update was successful
        if self.source:
            # reread everything
            self._keys = []

            if self.remote is False:
                if self.fileformat == "jwk":
                    self.do_local_jwk(self.source)
                elif self.fileformat == "der":
                    self.do_local_der(self.source, self.keytype, self.keyusage)
            else:
                res = self.do_remote()
        return res

    def get(self, typ=""):
        """
        Return keys matching the typ.

        :param typ: Type of key (rsa, ec, oct, ..)
        :return: If typ is undefined all the keys as a dictionary otherwise the appropriate keys in a list
        """
        self._uptodate()
        _typs = [typ.lower(), typ.upper()]

        if typ:
            return [k for k in self._keys if k.kty in _typs]
        else:
            return self._keys

    def keys(self):
        self._uptodate()

        return self._keys

    def available_keys(self):
        return self._keys

    def remove_key(self, typ, val=None):
        """
        Delete key given the type ot type and value.

        :param typ: Type of key (rsa, ec, oct, ..)
        :param val: The key itself
        """
        if val:
            self._keys = [
                k for k in self._keys if not (k.kty == typ and k.key == val.key)
            ]
        else:
            self._keys = [k for k in self._keys if not k.kty == typ]

    def __str__(self):
        return str(self.jwks())

    def jwks(self, private=False):
        self._uptodate()
        keys = list()
        for k in self._keys:
            if private:
                key = k.serialize(private)
            else:
                key = k.to_dict()
                for k, v in key.items():
                    key[k] = as_unicode(v)
            keys.append(key)
        return json.dumps({"keys": keys})

    def append(self, key):
        self._keys.append(key)

    def remove(self, key):
        self._keys.remove(key)

    def __len__(self):
        return len(self._keys)

    def get_key_with_kid(self, kid):
        for key in self._keys:
            if key.kid == kid:
                return key

        # Try updating since there might have been an update to the key file
        self.update()

        for key in self._keys:
            if key.kid == kid:
                return key

        return None

    def kids(self):
        self._uptodate()
        return [key.kid for key in self._keys if key.kid != ""]

    def remove_outdated(self, after):
        """
        Remove keys that should not be available any more.

        Outdated means that the key was marked as inactive at a time that was longer ago then what is given in 'after'.

        :param after: The length of time the key will remain in the KeyBundle before it should be removed.
        """
        now = time.time()
        if not isinstance(after, float):
            try:
                after = float(after)
            except TypeError:
                raise

        _kl = []
        for k in self._keys:
            if k.inactive_since and k.inactive_since + after < now:
                continue
            else:
                _kl.append(k)

        self._keys = _kl


def keybundle_from_local_file(filename, typ, usage):
    if typ.upper() == "RSA":
        kb = KeyBundle()
        k = RSAKey()
        k.load(filename)
        k.use = usage[0]
        kb.append(k)
        for use in usage[1:]:
            _k = RSAKey()
            _k.use = use
            _k.load_key(k.key)
            kb.append(_k)
    elif typ.lower() == "jwk":
        kb = KeyBundle(source=filename, fileformat="jwk", keyusage=usage)
    else:
        raise UnknownKeyType("Unsupported key type")

    return kb


def dump_jwks(kbl, target, private=False):
    """
    Write a JWK to a file.

    :param kbl: List of KeyBundles
    :param target: Name of the file to which everything should be written
    :param private: Should also the private parts be exported
    """
    keys = []
    for kb in kbl:
        keys.extend(
            [
                k.serialize(private)
                for k in kb.keys()
                if k.kty != "oct" and not k.inactive_since
            ]
        )
    res = {"keys": keys}

    try:
        f = open(target, "w")
    except IOError:
        (head, tail) = os.path.split(target)
        os.makedirs(head)
        f = open(target, "w")

    _txt = json.dumps(res)
    f.write(_txt)
    f.close()


class KeyJar(object):
    """A keyjar contains a number of KeyBundles."""

    def __init__(
        self, verify_ssl=True, keybundle_cls=KeyBundle, remove_after=3600, timeout=5
    ):
        """
        Initialize the class.

        :param verify_ssl: Do SSL certificate verification
        :param timeout: Timeout for requests library. Can be specified either as
            a single integer or as a tuple of integers. For more details, refer to
            ``requests`` documentation.
        :return:
        """
        self.issuer_keys: Dict[str, List[KeyBundle]] = {}
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.keybundle_cls = keybundle_cls
        self.remove_after = remove_after

    def __repr__(self):
        issuers = list(self.issuer_keys.keys())
        return "<KeyJar(issuers={})>".format(issuers)

    def add_if_unique(self, issuer, use, keys):
        if use in self.issuer_keys[issuer] and self.issuer_keys[issuer][use]:
            for typ, key in keys:
                flag = 1
                for _typ, _key in self.issuer_keys[issuer][use]:
                    if _typ == typ and key is _key:
                        flag = 0
                        break
                if flag:
                    self.issuer_keys[issuer][use].append((typ, key))
        else:
            self.issuer_keys[issuer][use] = keys

    def add(self, issuer, url, **kwargs):
        """
        Add keys for issuer.

        :param issuer: Who issued the keys
        :param url: Where can the key/-s be found
        :param kwargs: extra parameters for instantiating KeyBundle
        """
        if not url:
            raise KeyError("No jwks_uri")

        if "/localhost:" in url or "/localhost/" in url:
            kc = self.keybundle_cls(
                source=url, verify_ssl=False, timeout=self.timeout, **kwargs
            )
        else:
            kc = self.keybundle_cls(
                source=url, verify_ssl=self.verify_ssl, timeout=self.timeout, **kwargs
            )

        try:
            self.issuer_keys[issuer].append(kc)
        except KeyError:
            self.issuer_keys[issuer] = [kc]

        return kc

    def add_symmetric(self, issuer, key, usage=None):
        if issuer not in self.issuer_keys:
            self.issuer_keys[issuer] = []

        _key = b64e(as_bytes(key))
        if usage is None:
            self.issuer_keys[issuer].append(
                self.keybundle_cls([{"kty": "oct", "k": _key}])
            )
        else:
            for use in usage:
                self.issuer_keys[issuer].append(
                    self.keybundle_cls([{"kty": "oct", "k": _key, "use": use}])
                )

    def add_kb(self, issuer, kb):
        try:
            self.issuer_keys[issuer].append(kb)
        except KeyError:
            self.issuer_keys[issuer] = [kb]

    def __setitem__(self, issuer, val):
        if isinstance(val, str):
            val = [val]
        elif not isinstance(val, list):
            val = [val]

        self.issuer_keys[issuer] = val

    def items(self):
        return self.issuer_keys.items()

    def get(self, key_use, key_type="", issuer="", kid=None, **kwargs):
        """
        Return keys matching the args.

        :param key_use: A key useful for this usage (enc, dec, sig, ver)
        :param key_type: Type of key (rsa, ec, symmetric, ..)
        :param issuer: Who is responsible for the keys, "" == me
        :param kid: A Key Identifier
        :return: A possibly empty list of keys
        """
        if key_use in ["dec", "enc"]:
            use = "enc"
        else:
            use = "sig"

        if issuer != "":
            try:
                _keys = self.issuer_keys[issuer]
            except KeyError:
                if issuer.endswith("/"):
                    try:
                        _keys = self.issuer_keys[issuer[:-1]]
                    except KeyError:
                        _keys = []
                else:
                    try:
                        _keys = self.issuer_keys[issuer + "/"]
                    except KeyError:
                        _keys = []
        else:
            try:
                _keys = self.issuer_keys[issuer]
            except KeyError:
                _keys = []

        lst: List[KEYS] = []
        if _keys:
            for bundle in _keys:
                if key_type:
                    _bkeys = bundle.get(key_type)
                else:
                    _bkeys = bundle.keys()
                for key in _bkeys:
                    if key.inactive_since and key_use != "ver":
                        # Skip inactive keys unless for signature verification
                        continue
                    if kid and key.kid == kid:
                        lst = [key]
                        break
                    if not key.use or use == key.use:
                        lst.append(key)
                        continue
                    # Verification can be performed by both `sig` and `ver` keys
                    if key_use == "ver" and key.use in ("sig", "ver"):
                        lst.append(key)

        # if elliptic curve have to check I have a key of the right curve
        if key_type == "EC" and "alg" in kwargs:
            name = "P-{}".format(kwargs["alg"][2:])  # the type
            _lst = []
            for key in lst:
                if name == key.crv:
                    _lst.append(key)
            lst = _lst

        if use == "enc" and key_type == "oct" and issuer != "":
            # Add my symmetric keys
            for kb in self.issuer_keys[""]:
                for key in kb.get(key_type):
                    if key.inactive_since:
                        continue
                    if not key.use or key.use == use:
                        lst.append(key)

        return lst

    def get_signing_key(self, key_type="", owner="", kid=None, **kwargs):
        return self.get("sig", key_type, owner, kid, **kwargs)

    def get_verify_key(self, key_type="", owner="", kid=None, **kwargs):
        return self.get("ver", key_type, owner, kid, **kwargs)

    def get_encrypt_key(self, key_type="", owner="", kid=None, **kwargs):
        return self.get("enc", key_type, owner, kid, **kwargs)

    def get_decrypt_key(self, key_type="", owner="", kid=None, **kwargs):
        return self.get("dec", key_type, owner, kid, **kwargs)

    def get_key_by_kid(self, kid, owner=""):
        """
        Return the key from a specific owner that has a specific kid.

        :param kid: The key identifier
        :param owner: The owner of the key
        :return: a specific key instance or None
        """
        for kb in self.issuer_keys[owner]:
            _key = kb.get_key_with_kid(kid)
            if _key:
                return _key
        return None

    def __contains__(self, item):
        if item in self.issuer_keys:
            return True
        else:
            return False

    def x_keys(self, var, part):
        _func = getattr(self, "get_%s_key" % var)

        keys = _func(key_type="", owner=part)
        keys.extend(_func(key_type="", owner=""))
        return keys

    def verify_keys(self, part):
        """
        Keys for me and someone else.

        :param part: The other part
        :return: dictionary of keys
        """
        return self.x_keys("verify", part)

    def decrypt_keys(self, part):
        """
        Keys for me and someone else.

        :param part: The other part
        :return: dictionary of keys
        """
        return self.x_keys("decrypt", part)

    def __getitem__(self, issuer):
        try:
            return self.issuer_keys[issuer]
        except KeyError:
            logger.debug(
                "Issuer '{}' not found, available key issuers: {}".format(
                    issuer, list(self.issuer_keys.keys())
                )
            )
            raise

    def remove_key(self, issuer, key_type, key):
        try:
            kcs = self.issuer_keys[issuer]
        except KeyError:
            return

        for kc in kcs:
            kc.remove_key(key_type, key)
            if len(kc) == 0:
                self.issuer_keys[issuer].remove(kc)

    def update(self, kj):
        for key, val in kj.issuer_keys.items():
            if isinstance(val, str):
                val = [val]
            elif not isinstance(val, list):
                val = [val]

            try:
                self.issuer_keys[key].extend(val)
            except KeyError:
                self.issuer_keys[key] = val

    def match_owner(self, url):
        for owner in self.issuer_keys.keys():
            if url.startswith(owner):
                return owner

        raise KeyIOError("No keys for '%s'" % url)

    def __str__(self):
        _res = {}
        for _id, kbs in self.issuer_keys.items():
            _l: List[Dict[str, str]] = []
            for kb in kbs:
                _l.extend(json.loads(kb.jwks())["keys"])
            _res[_id] = {"keys": _l}
        return "%s" % (_res,)

    def keys(self):
        return self.issuer_keys.keys()

    def load_keys(self, pcr, issuer, replace=False):
        """
        Fetch keys from another server.

        :param pcr: The provider information
        :param issuer: The provider URL
        :param replace: If all previously gathered keys from this provider
            should be replace.
        :return: Dictionary with usage as key and keys as values
        """
        logger.debug("loading keys for issuer: %s" % issuer)
        try:
            logger.debug("pcr: %s" % pcr)
        except MessageException:
            pass

        if replace or issuer not in self.issuer_keys:
            self.issuer_keys[issuer] = []

        try:
            self.add(issuer, pcr["jwks_uri"])
        except KeyError:
            # jwks should only be considered if no jwks_uri is present
            try:
                _keys = pcr["jwks"]["keys"]
                self.issuer_keys[issuer].append(
                    self.keybundle_cls(
                        _keys, verify_ssl=self.verify_ssl, timeout=self.timeout
                    )
                )
            except KeyError:
                pass

    def find(self, source, issuer):
        """
        Find a key bundle.

        :param source: A url
        :param issuer: The issuer of keys
        """
        try:
            for kb in self.issuer_keys[issuer]:
                if kb.source == source:
                    return kb
        except KeyError:
            return None

    def dump_issuer_keys(self, issuer):
        res = []
        try:
            for kb in self.issuer_keys[issuer]:
                res.extend([k.to_dict() for k in kb.keys()])
        except KeyError:
            pass

        return res

    def export_jwks(self, private=False, issuer=""):
        keys = []
        for kb in self.issuer_keys[issuer]:
            keys.extend(
                [k.serialize(private) for k in kb.keys() if k.inactive_since == 0]
            )
        return {"keys": keys}

    def import_jwks(self, jwks, issuer):
        """
        Import key from JWKS.

        :param jwks: Dictionary representation of a JWKS
        :param issuer: Who 'owns' the JWKS
        """
        try:
            _keys = jwks["keys"]
        except KeyError:
            raise ValueError("Not a proper JWKS")
        else:
            try:
                self.issuer_keys[issuer].append(
                    self.keybundle_cls(
                        _keys, verify_ssl=self.verify_ssl, timeout=self.timeout
                    )
                )
            except KeyError:
                self.issuer_keys[issuer] = [
                    self.keybundle_cls(
                        _keys, verify_ssl=self.verify_ssl, timeout=self.timeout
                    )
                ]

    def add_keyjar(self, keyjar):
        for iss, kblist in keyjar.items():
            try:
                self.issuer_keys[iss].extend(kblist)
            except KeyError:
                self.issuer_keys[iss] = kblist

    def dump(self):
        res = {}
        for issuer in self.issuer_keys.keys():
            res[issuer] = self.dump_issuer_keys(issuer)
        return res

    def restore(self, info):
        for issuer, keys in info.items():
            self.issuer_keys[issuer] = [
                self.keybundle_cls(
                    keys, verify_ssl=self.verify_ssl, timeout=self.timeout
                )
            ]

    def copy(self):
        copy_keyjar = KeyJar(verify_ssl=self.verify_ssl, timeout=self.timeout)
        for issuer, keybundles in self.issuer_keys.items():
            _kb = self.keybundle_cls(verify_ssl=self.verify_ssl, timeout=self.timeout)
            for kb in keybundles:
                for k in kb.keys():
                    _kb.append(copy.copy(k))
            copy_keyjar.issuer_keys[issuer] = [_kb]

        return copy_keyjar

    def keys_by_alg_and_usage(self, issuer, alg, usage):
        if usage in ["sig", "ver"]:
            ktype = jws.alg2keytype(alg)
        else:
            ktype = jwe.alg2keytype(alg)

        return self.get(usage, ktype, issuer)

    def get_issuer_keys(self, issuer):
        res: List[KEYS] = []
        for kbl in self.issuer_keys[issuer]:
            res.extend(kbl.keys())
        return res

    def __eq__(self, other):
        if not isinstance(other, KeyJar):
            return False

        # The set of issuers MUST be the same
        if set(self.keys()) != set(other.keys()):
            return False

        # Keys per issuer must be the same
        for iss in self.keys():
            sk = self.get_issuer_keys(iss)
            ok = other.get_issuer_keys(iss)
            if len(sk) != len(ok):
                return False

            if not any(k in ok for k in sk):
                return False

        return True

    def remove_outdated(self):
        """
        Goes through the complete list of issuers and for each of them removes outdated keys.

        Outdated keys are keys that has been marked as inactive at a time that
        is longer ago then some set number of seconds.
        The number of seconds a carried in the remove_after parameter.
        """
        for iss in list(self.keys()):
            _kbl = []
            for kb in self.issuer_keys[iss]:
                kb.remove_outdated(self.remove_after)
                if len(kb):
                    _kbl.append(kb)
            if _kbl:
                self.issuer_keys[iss] = _kbl
            else:
                del self.issuer_keys[iss]


# =============================================================================


class RedirectStdStreams(object):
    def __init__(self, stdout=None, stderr=None):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, trace_back):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


def key_setup(vault, **kwargs):
    """
    Create a KeyBundle from file.

    :param vault: Where the keys are kept
    :return: 2-tuple: result of urlsplit and a dictionary with parameter name as key and url and value
    """
    vault_path = proper_path(vault)

    if not os.path.exists(vault_path):
        os.makedirs(vault_path)

    kb = KeyBundle()
    for usage in ["sig", "enc"]:
        if usage in kwargs:
            if kwargs[usage] is None:
                continue

            _args = kwargs[usage]
            if _args["alg"].upper() == "RSA":
                try:
                    _key = rsa_load("%s%s" % (vault_path, "pyoidc"))
                except Exception:
                    with open(os.devnull, "w") as devnull:
                        with RedirectStdStreams(stdout=devnull, stderr=devnull):
                            _key = create_and_store_rsa_key_pair(path=vault_path)

                k = RSAKey(key=_key, use=usage)
                k.add_kid()
                kb.append(k)
    return kb


def key_export(baseurl, local_path, vault, keyjar, **kwargs):
    """
    Export keys.

    :param baseurl: The base URL to which the key file names are added
    :param local_path: Where on the machine the export files are kept
    :param vault: Where the keys are kept
    :param keyjar: Where to store the exported keys
    :return: 2-tuple: result of urlsplit and a dictionary with
        parameter name as key and url and value
    """
    part = urlsplit(baseurl)

    # deal with the export directory
    if part.path.endswith("/"):
        _path = part.path[:-1]
    else:
        _path = part.path[:]

    local_path = proper_path("%s/%s" % (_path, local_path))

    if not os.path.exists(local_path):
        os.makedirs(local_path)

    kb = key_setup(vault, **kwargs)

    try:
        keyjar[""].append(kb)
    except KeyError:
        keyjar[""] = kb

    # the local filename
    _export_filename = os.path.join(local_path, "jwks")

    with open(_export_filename, "w") as f:
        f.write(str(kb))

    _url = "%s://%s%s" % (part.scheme, part.netloc, _export_filename[1:])

    return _url


# ================= create RSA key ======================


def create_and_store_rsa_key_pair(name="pyoidc", path=".", size=2048):
    """
    Create RSA keypair.

    :param name: Name of the key file
    :param path: Path to where the key files are stored
    :param size: RSA key size
    :return: RSA key
    """
    key = RSA.generate(size)

    os.makedirs(path, exist_ok=True)

    if name:
        with open(os.path.join(path, name), "wb") as f:
            f.write(key.exportKey("PEM"))

        _pub_key = key.publickey()
        with open(os.path.join(path, "{}.pub".format(name)), "wb") as f:
            f.write(_pub_key.exportKey("PEM"))

    return key


def proper_path(path):
    """
    Clean up the path specification so it looks like something I could use.

    "./" <path> "/"
    """
    if path.startswith("./"):
        pass
    elif path.startswith("/"):
        path = ".%s" % path
    elif path.startswith("."):
        while path.startswith("."):
            path = path[1:]
        if path.startswith("/"):
            path = ".%s" % path
    else:
        path = "./%s" % path

    if not path.endswith("/"):
        path += "/"

    return path


def ec_init(spec):
    """
    Initialize EC encryption.

    :param spec: Key specifics of the form
    {"type": "EC", "crv": "P-256", "use": ["sig"]},
    :return: A KeyBundle instance
    """
    _key = NISTEllipticCurve.by_name(spec["crv"])
    kb = KeyBundle(keytype="EC", keyusage=spec["use"])
    for use in spec["use"]:
        priv, pub = _key.key_pair()
        ec = ECKey(x=pub[0], y=pub[1], d=priv, crv=spec["crv"])
        ec.serialize()
        ec.use = use
        kb.append(ec)
    return kb


def rsa_init(spec):
    """
    Initialize RSA encryption.

    :param spec:
    :return: KeyBundle
    """
    arg = {}
    for param in ["name", "path", "size"]:
        try:
            arg[param] = spec[param]
        except KeyError:
            pass

    kb = KeyBundle(keytype="RSA", keyusage=spec["use"])
    for use in spec["use"]:
        _key = create_and_store_rsa_key_pair(**arg)
        kb.append(RSAKey(use=use, key=_key))
    return kb


def keyjar_init(instance, key_conf, kid_template=""):
    """
    Initialize KeyJar.

    Configuration of the type:
    keys = [
        {"type": "RSA", "key": "cp_keys/key.pem", "use": ["enc", "sig"]},
        {"type": "EC", "crv": "P-256", "use": ["sig"]},
        {"type": "EC", "crv": "P-256", "use": ["enc"]}
    ]

    :param instance: server/client instance
    :param key_conf: The key configuration
    :param kid_template: A template by which to build the kids
    :return: a JWKS
    """
    jwks, keyjar, kdd = build_keyjar(
        key_conf, kid_template, instance.keyjar, instance.kid
    )

    instance.keyjar = keyjar
    instance.kid = kdd
    return jwks


def _new_rsa_key(spec):
    if "name" not in spec:
        if "/" in spec["key"]:
            (head, tail) = os.path.split(spec["key"])
            spec["path"] = head
            spec["name"] = tail
        else:
            spec["name"] = spec["key"]
    return rsa_init(spec)


def build_keyjar(key_conf, kid_template="", keyjar=None, kidd=None):
    """
    Create a KeyJar from keys.

    Configuration of the type:
    keys = [
        {"type": "RSA", "key": "cp_keys/key.pem", "use": ["enc", "sig"]},
        {"type": "EC", "crv": "P-256", "use": ["sig"]},
        {"type": "EC", "crv": "P-256", "use": ["enc"]}
    ]

    :param key_conf: The key configuration
    :param kid_template: A template by which to build the kids
    :return: a tuple consisting of a JWKS dictionary, a KeyJar instance
        and a representation of which kids that can be used for what.
        Note the JWKS contains private key information !!
    """
    if keyjar is None:
        keyjar = KeyJar()

    if kidd is None:
        kidd = {"sig": {}, "enc": {}}

    kid = 0
    jwks: Dict[str, List[Dict[str, str]]] = {"keys": []}

    for spec in key_conf:
        typ = spec["type"].upper()

        if typ == "RSA":
            if "key" in spec:
                error_to_catch = getattr(
                    builtins, "FileNotFoundError", getattr(builtins, "IOError")
                )
                try:
                    kb = KeyBundle(
                        source="file://%s" % spec["key"],
                        fileformat="der",
                        keytype=typ,
                        keyusage=spec["use"],
                    )
                except error_to_catch:
                    kb = _new_rsa_key(spec)
                except Exception:
                    raise
            else:
                kb = rsa_init(spec)
        elif typ == "EC":
            kb = ec_init(spec)

        for k in kb.keys():
            if kid_template:
                k.kid = kid_template % kid
                kid += 1
            else:
                k.add_kid()
            kidd[k.use][k.kty] = k.kid

        jwks["keys"].extend([k.serialize() for k in kb.keys() if k.kty != "oct"])

        keyjar.add_kb("", kb)

    return jwks, keyjar, kidd


def update_keyjar(keyjar):
    for iss, kbl in keyjar.items():
        for kb in kbl:
            kb.update()


def key_summary(keyjar, issuer):
    try:
        kbl = keyjar[issuer]
    except KeyError:
        return ""
    else:
        key_list = []
        for kb in kbl:
            for key in kb.keys():
                if key.inactive_since:
                    key_list.append("*{}:{}:{}".format(key.kty, key.use, key.kid))
                else:
                    key_list.append("{}:{}:{}".format(key.kty, key.use, key.kid))
        return ", ".join(key_list)


def check_key_availability(inst, jwt):
    """
    Try to refresh keys.

    If the server is restarted it will NOT load keys from jwks_uris for
    all the clients that has been registered. So this function is there
    to get a clients keys when needed.

    :param inst: OP instance
    :param jwt: A JWT that has to be verified or decrypted
    """
    _rj = jws.factory(jwt)
    payload = json.loads(as_unicode(_rj.jwt.part[1]))
    _cid = payload["iss"]
    if _cid not in inst.keyjar:
        cinfo = inst.cdb[_cid]
        inst.keyjar.add_symmetric(_cid, cinfo["client_secret"], ["enc", "sig"])
        if cinfo.get("jwks_uri") is not None:
            inst.keyjar.add(_cid, cinfo["jwks_uri"])
        elif cinfo.get("jwks") is not None:
            inst.keyjar.import_jwks(cinfo["jwks"], _cid)

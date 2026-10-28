"""Keeps PRONOTE instances that still use the login alea working.

Since 2026-09-02, PRONOTE instances no longer use the "alea" in the login
challenge: they expect the raw challenge string to be re-encrypted as is,
instead of being decrypted, stripped of its alea, then re-encrypted.

pronotepy 2.15.7 handles the new behaviour, but only that one: it dropped the
old code path entirely, so instances that have not been migrated yet stop
working. This module replaces ``ClientBase._login`` with the 2.15.7
implementation supporting both: the old path is tried first, and the raw
challenge is used when it fails.

Keeping that order matters. Deciding between the two schemes is done locally,
before anything is sent, so a single Authentification request is issued either
way and PRONOTE never records a failed login attempt.

See https://github.com/bain3/pronotepy/issues/346 and
https://github.com/delphiki/hass-pronote/issues/172.

The version guard at the bottom of this file disables the patch as soon as
pronotepy moves on, so this module has to be reviewed on every bump. It can be
dropped once no establishment is left on the old challenge scheme.
"""

import json
import logging
from typing import Optional

from Crypto.Hash import SHA256

import pronotepy
from pronotepy import dataClasses
from pronotepy.clients import ClientBase
from pronotepy.exceptions import CryptoError, PronoteAPIError
from pronotepy.pronoteAPI import _Encryption, _enleverAlea, _prepare_onglets, log

_LOGGER = logging.getLogger(__name__)

# pronotepy version this patched _login has been copied from.
PATCHED_PRONOTEPY_VERSION = "2.15.7"


def _login(self) -> bool:
    """Logs in the user.

    Returns:
        bool: True if logged in, False if not
    """

    if self.ent:
        username = self.attributes["e"]
        password = self.attributes["f"]
    else:
        username = self.username
        password = self.password

    # identification phase
    ident_json = {
        "genreConnexion": 0,
        "genreEspace": int(self.attributes["a"]),
        "identifiant": username,
        "pourENT": True if self.ent else False,
        "enConnexionAuto": False,
        "demandeConnexionAuto": False,
        "demandeConnexionAppliMobile": self.login_mode == "qr_code",
        "demandeConnexionAppliMobileJeton": self.login_mode == "qr_code",
        "enConnexionAppliMobile": self.login_mode == "token",
        "uuidAppliMobile": (
            self.uuid if self.login_mode in ("qr_code", "token") else ""
        ),
        "loginTokenSAV": "",
    }
    idr = self.post("Identification", data=ident_json)
    log.debug("indentification")

    # creating the authentification data
    log.debug(str(idr))
    challenge = idr["dataSec"]["data"]["challenge"]
    e = _Encryption()
    e.aes_set_iv(self.communication.encryption.aes_iv)

    # key gen
    if self.ent:
        motdepasse = SHA256.new(str(password).encode()).hexdigest().upper()
        e.aes_set_key(motdepasse.encode())
    else:
        if idr["dataSec"]["data"]["modeCompLog"]:
            username = username.lower()
        if idr["dataSec"]["data"]["modeCompMdp"]:
            password = password.lower()
        alea = idr["dataSec"]["data"].get("alea", "")
        motdepasse = SHA256.new((alea + password).encode()).hexdigest().upper()
        e.aes_set_key((username + motdepasse).encode())

    # challenge
    challenge_error: Optional[CryptoError] = None
    try:
        dec = e.aes_decrypt(bytes.fromhex(challenge))
        dec_no_alea = _enleverAlea(dec.decode())
        ch = e.aes_encrypt(dec_no_alea.encode()).hex()
    except (CryptoError, ValueError) as ex:
        # ValueError catches the UnicodeDecodeError raised when unpadding
        # happens to succeed on the garbage bytes a migrated instance yields:
        # decrypting its challenge with the derived key is meaningless, so the
        # last byte is a valid padding length once in a while.
        if self.login_mode == "qr_code":
            hint = "exception happened during login -> probably the qr code has expired (qr code is valid during 10 minutes)"
        else:
            hint = "exception happened during login -> probably bad username/password"
        if isinstance(ex, CryptoError):
            ex.args += (hint,)
            challenge_error = ex
        else:
            challenge_error = CryptoError(str(ex), hint)
        # Migrated PRONOTE instances do not use the alea anymore, they expect
        # the raw challenge to be re-encrypted as is. Try that before giving
        # up, and keep the error around so that it can still be raised (with
        # its helpful message) if the authentification below fails anyway.
        log.debug("challenge decryption failed, falling back to the raw challenge")
        ch = e.aes_encrypt(challenge.encode()).hex()

    # send
    auth_json = {
        "connexion": 0,
        "challenge": ch,
        "espace": int(self.attributes["a"]),
    }
    try:
        auth_response = self.post("Authentification", data=auth_json)
    except PronoteAPIError:
        if challenge_error is not None:
            raise challenge_error
        raise
    if "cle" in auth_response["dataSec"]["data"]:
        self.communication.after_auth(auth_response, e.aes_key)
        self.encryption.aes_key = e.aes_key

        actionsDoubleAuth = auth_response["dataSec"]["data"].get("actionsDoubleAuth")
        if actionsDoubleAuth:
            actions = json.loads(actionsDoubleAuth["V"])

            doRegisterDevice = 5 in actions or 3 in actions
            doVerifyPin = 3 in actions

            self._do_2fa(
                doVerifyPin,
                doRegisterDevice,
                self.account_pin,
                self.device_name,
            )

        log.info(f"successfully logged in as {self.username}")

        last_conn = auth_response["dataSec"]["data"].get("derniereConnexion")
        self.last_connection = (
            dataClasses.Util.datetime_parse(last_conn["V"]) if last_conn else None
        )

        if self.login_mode in ("qr_code", "token") and auth_response["dataSec"][
            "data"
        ].get("jetonConnexionAppliMobile"):
            self.password = auth_response["dataSec"]["data"][
                "jetonConnexionAppliMobile"
            ]

        # getting listeOnglets separately because of pronote API change
        self.parametres_utilisateur = self.post("ParametresUtilisateur")
        self.info = dataClasses.ClientInfo(
            self, self.parametres_utilisateur["dataSec"]["data"]["ressource"]
        )
        self.communication.authorized_onglets = _prepare_onglets(
            self.parametres_utilisateur["dataSec"]["data"]["listeOnglets"]
        )
        log.info("got onglets data.")
        return True
    else:
        if challenge_error is not None:
            raise challenge_error
        log.info("login failed")
        return False


if pronotepy.__version__ == PATCHED_PRONOTEPY_VERSION:
    ClientBase._login = _login
    _LOGGER.debug("pronotepy login hotfix applied")
else:
    _LOGGER.warning(
        "pronotepy login hotfix not applied: expected version %s, got %s. "
        "It needs to be reviewed against the new version, or removed.",
        PATCHED_PRONOTEPY_VERSION,
        pronotepy.__version__,
    )

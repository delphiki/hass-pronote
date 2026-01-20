"""Client wrapper for the Pronote integration."""

### Hotfix for python 3.13 https://github.com/bain3/pronotepy/pull/317#issuecomment-2523257656
import autoslot
from itertools import tee
import dis


def assignments_to_self(method) -> set:
    instance_var = next(iter(method.__code__.co_varnames), "self")
    instructions = dis.Bytecode(method)
    i0, i1 = tee(instructions)
    next(i1, None)
    names = set()
    for a, b in zip(i0, i1):
        accessing_self = (
            a.opname in ("LOAD_FAST", "LOAD_DEREF") and a.argval == instance_var
        ) or (a.opname == "LOAD_FAST_LOAD_FAST" and a.argval[1] == instance_var)
        storing_attribute = b.opname == "STORE_ATTR"
        if accessing_self and storing_attribute:
            names.add(b.argval)
    return names


autoslot.assignments_to_self = assignments_to_self
### End Hotfix

import pronotepy
import json
import logging
import re

_LOGGER = logging.getLogger(__name__)


def get_pronote_client(data) -> pronotepy.Client | pronotepy.ParentClient | None:
    _LOGGER.debug(f"Coordinator uses connection: {data['connection_type']}")

    if data["connection_type"] == "qrcode":
        client = get_client_from_qr_code(data)
    else:
        client = get_client_from_username_password(data)

    if client is None:
        _LOGGER.warning("Client creation failed")
        return None

    try:
        client.session_check()
    except Exception as e:
        _LOGGER.error("Session check failed: %s", e)

    return client


def get_client_from_username_password(
    data,
) -> pronotepy.Client | pronotepy.ParentClient | None:
    url = data["url"]
    url = re.sub(r"/[^/]+\.html$", "/", url)
    if not url.endswith("/"):
        url += "/"
    url = url + ("parent" if data["account_type"] == "parent" else "eleve") + ".html"

    ent = None
    if "ent" in data:
        ent = getattr(pronotepy.ent, data["ent"])

    if not ent:
        url += "?login=true"

    try:
        client = (
            pronotepy.ParentClient
            if data["account_type"] == "parent"
            else pronotepy.Client
        )(
            pronote_url=url,
            username=data["username"],
            password=data["password"],
            account_pin=data.get("account_pin", None),
            device_name=data.get("device_name", None),
            client_identifier=data.get("client_identifier", None),
            ent=ent,
        )
        del ent
        del client.account_pin
        _LOGGER.info(client.info.name)
    except Exception as err:
        _LOGGER.critical(err)
        return None

    return client


def get_client_from_qr_code(data) -> pronotepy.Client | pronotepy.ParentClient | None:

    if "qr_code_json" in data:  # first login from QR Code JSON

        # login with qrcode json
        qr_code_json = json.loads(data["qr_code_json"])
        qr_code_pin = data["qr_code_pin"]
        uuid = data["qr_code_uuid"]

        # get the initial client using qr_code
        client = (
            pronotepy.ParentClient
            if data["account_type"] == "parent"
            else pronotepy.Client
        ).qrcode_login(
            qr_code=qr_code_json,
            pin=qr_code_pin,
            uuid=uuid,
            account_pin=data.get("account_pin", None),
            client_identifier=data.get("client_identifier", None),
            device_name=data.get("device_name", None),
        )

        qr_code_url = client.pronote_url
        qr_code_username = client.username
        qr_code_password = client.password
        qr_code_uuid = client.uuid
        qr_code_account_pin = client.account_pin
        qr_code_device_name = client.device_name
        qr_code_client_identifier = client.client_identifier
    else:
        qr_code_url = data["qr_code_url"]
        qr_code_username = data["qr_code_username"]
        qr_code_password = data["qr_code_password"]
        qr_code_uuid = data["qr_code_uuid"]
        qr_code_account_pin = data.get("account_pin", None)
        qr_code_device_name = data.get("device_name", None)
        qr_code_client_identifier = data.get("client_identifier", None)

    _LOGGER.info(f"Coordinator uses qr_code_username: {qr_code_username}")
    _LOGGER.info(f"Coordinator uses qr_code_pwd: {qr_code_password}")

    return (
        pronotepy.ParentClient if data["account_type"] == "parent" else pronotepy.Client
    ).token_login(
        pronote_url=qr_code_url,
        username=qr_code_username,
        password=qr_code_password,
        uuid=qr_code_uuid,
        account_pin=qr_code_account_pin,
        device_name=qr_code_device_name,
        client_identifier=qr_code_client_identifier,
    )


def get_day_start_at(lessons):
    day_start_at = None

    if lessons is not None:
        for lesson in lessons:
            if not lesson.canceled:
                day_start_at = lesson.start
                break

    return day_start_at

"""Client wrapper for the Pronote integration."""

import pronotepy
import json
import logging
import re

_LOGGER = logging.getLogger(__name__)

def get_pronote_client(data) -> pronotepy.Client | pronotepy.ParentClient | None:
    _LOGGER.debug(f"Coordinator uses connection: {data['connection_type']}")

    if data['connection_type'] == 'qrcode':
        return get_client_from_qr_code(data)
    else:
        return get_client_from_username_password(data)

def get_client_from_username_password(data) -> pronotepy.Client | pronotepy.ParentClient | None:
    url = data['url']
    url = re.sub(r'/[^/]+\.html$', '/', url)
    if not url.endswith('/'):
        url += '/'
    url = url + ('parent' if data['account_type'] == 'parent' else 'eleve') + '.html'

    ent = None
    if 'ent' in data:
        ent = getattr(pronotepy.ent, data['ent'])

    if not ent:
        url += '?login=true'

    try:
        client = (pronotepy.ParentClient if data['account_type'] == 'parent' else pronotepy.Client)(
            url,
            data['username'],
            data['password'],
            ent
        )
        del ent
        _LOGGER.info(client.info.name)
    except Exception as err:
        _LOGGER.critical(err)
        return None

    return client

def get_client_from_qr_code(data) -> pronotepy.Client | pronotepy.ParentClient | None:

    if 'qr_code_json' in data: # first login from QR Code JSON

        # login with qrcode json
        qr_code_json = json.loads(data['qr_code_json'])
        qr_code_pin = data['qr_code_pin']
        uuid = data['qr_code_uuid']

        # get the initial client using qr_code
        client = (pronotepy.ParentClient if data['account_type'] == 'parent' else pronotepy.Client).qrcode_login(
            qr_code_json,
            qr_code_pin,
            uuid
        )

        qr_code_url = client.pronote_url
        qr_code_username = client.username
        qr_code_password = client.password
        qr_code_uuid = client.uuid
    else:
        qr_code_url = data['qr_code_url']
        qr_code_username = data['qr_code_username']
        qr_code_password = data['qr_code_password']
        qr_code_uuid = data['qr_code_uuid']

    _LOGGER.info(f"Coordinator uses qr_code_username: {qr_code_username}")
    _LOGGER.info(f"Coordinator uses qr_code_pwd: {qr_code_password}")

    return (pronotepy.ParentClient if data['account_type'] == 'parent' else pronotepy.Client).token_login(
        qr_code_url,
        qr_code_username,
        qr_code_password,
        qr_code_uuid
    )

def get_day_start_at(lessons):
    day_start_at = None

    if lessons is not None:
        for lesson in lessons:
            if not lesson.canceled:
                day_start_at = lesson.start
                break

    return day_start_at
"""ENT login functions missing from pronotepy.

pronotepy no longer maintains its ENT functions and enc_hauts_de_seine is
commented out there (https://github.com/bain3/pronotepy/issues/335).
Adapted from matthieumasnou-lgtm 
https://github.com/delphiki/hass-pronote/issues/193.
"""

from urllib.parse import urljoin

import pronotepy.ent
import requests
from bs4 import BeautifulSoup
from pronotepy.exceptions import ENTLoginError

ENC_HAUTS_DE_SEINE_HOST = "enc.hauts-de-seine.fr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0"
}


def _keycloak_form(response):
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.find("form", {"id": "kc-form-login"})


def enc_hauts_de_seine(username, password, pronote_url="", **opts):
    with requests.Session() as session:
        session.headers.update(HEADERS)
        # Pronote redirects to the ENC keycloak login page
        response = session.get(pronote_url, timeout=30)
        form = _keycloak_form(response)
        action = urljoin(response.url, form.get("action", "")) if form else ""
        # Only send the credentials to the ENC login form, over https
        if not action.startswith(f"https://{ENC_HAUTS_DE_SEINE_HOST}/"):
            raise ENTLoginError(
                f"ENC Hauts-de-Seine login form not found ({response.url})"
            )

        payload = {
            i["name"]: i.get("value", "")
            for i in form.find_all("input", {"name": True})
            if i.get("type") != "checkbox"
        }
        payload["username"] = username
        payload["password"] = password
        response = session.post(action, data=payload, timeout=30)

        if _keycloak_form(response):
            raise ENTLoginError(
                "Fail to connect with ENC Hauts-de-Seine: "
                "check your login/password"
            )

        return session.cookies


if not hasattr(pronotepy.ent, "enc_hauts_de_seine"):
    pronotepy.ent.enc_hauts_de_seine = enc_hauts_de_seine

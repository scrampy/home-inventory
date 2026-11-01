"""Checking that a request to /alexa really came from Amazon's Alexa service.

Amazon requires this of any skill hosted outside AWS Lambda. The checks follow
"Verify that the request was sent by Alexa" in the Alexa Skills Kit docs:

1. The SignatureCertChainUrl header points at Amazon's certificate bucket
   (https://s3.amazonaws.com/echo.api/...).
2. The certificate chain found there is valid today, leads to a trusted root,
   and is for echo-api.amazon.com.
3. The Signature-256 header is that certificate's RSA/SHA-256 signature of the
   exact request body.
4. The request's timestamp is within 150 seconds of now (so an old request
   can't be replayed).

Certificates are fetched once per URL and kept until they expire.
"""

import base64
import binascii
from datetime import datetime, timedelta, timezone
import posixpath
import re
from threading import Lock
import warnings
from urllib.parse import unquote, urlsplit

import certifi
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError
import requests

CERT_HOST = "s3.amazonaws.com"
CERT_PATH = "/echo.api/"
CERT_NAME = "echo-api.amazon.com"
MAX_REQUEST_AGE = timedelta(seconds=150)
MAX_CERT_BYTES = 64 * 1024

_cache = {}  # cert URL -> leaf certificate whose chain checked out
_lock = Lock()
_store = None


class NotFromAlexa(Exception):
    """The request failed a check. The message says which, for the log."""


def _now():
    return datetime.now(timezone.utc)


def check_cert_url(url):
    """Step 1: only Amazon's own certificate location is acceptable."""
    try:
        parts = urlsplit(url or "")
        port = parts.port
    except ValueError:
        raise NotFromAlexa("certificate URL is malformed")
    path = posixpath.normpath(unquote(parts.path)) if parts.path else ""
    if (parts.scheme.lower() != "https" or (parts.hostname or "").lower() != CERT_HOST
            or port not in (None, 443) or not path.startswith(CERT_PATH)):
        raise NotFromAlexa(f"certificate URL is not Amazon's: {url!r}")


def trust_store():
    """The public certificate authorities (from certifi). Tests replace this."""
    global _store
    if _store is None:
        with open(certifi.where(), "rb") as f:
            pem = f.read()
        roots = []
        # One at a time: a root cryptography dislikes (some have odd serial numbers) is skipped,
        # not allowed to stop the rest loading. Amazon's roots are ordinary.
        for block in re.findall(rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", pem, re.S):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    roots.append(x509.load_pem_x509_certificate(block))
                except ValueError:
                    pass
        _store = Store(roots)
    return _store


def fetch_chain(url):
    """The PEM certificate chain at `url`. Tests replace this."""
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    if len(response.content) > MAX_CERT_BYTES:
        raise NotFromAlexa("certificate chain is too large")
    return response.content


def _verified_leaf(url, now):
    """Step 2: the signing certificate at `url`, once its chain checks out."""
    with _lock:
        leaf = _cache.get(url)
    if leaf is not None and leaf.not_valid_before_utc <= now <= leaf.not_valid_after_utc:
        return leaf
    try:
        certs = x509.load_pem_x509_certificates(fetch_chain(url))
    except (requests.RequestException, ValueError) as e:
        raise NotFromAlexa(f"couldn't load the certificate chain: {e}")
    leaf, intermediates = certs[0], certs[1:]
    verifier = PolicyBuilder().store(trust_store()).time(now).build_server_verifier(x509.DNSName(CERT_NAME))
    try:
        verifier.verify(leaf, intermediates)
    except VerificationError as e:
        raise NotFromAlexa(f"certificate chain didn't check out: {e}")
    with _lock:
        _cache[url] = leaf
    return leaf


def verify(headers, body, timestamp, now=None):
    """Raise NotFromAlexa unless this request (headers, raw body bytes, request.timestamp) is from Alexa."""
    now = now or _now()
    url = headers.get("SignatureCertChainUrl")
    signature = headers.get("Signature-256")
    if not url or not signature:
        raise NotFromAlexa("signature headers are missing")
    check_cert_url(url)
    leaf = _verified_leaf(url, now)
    try:
        leaf.public_key().verify(base64.b64decode(signature, validate=True), body, padding.PKCS1v15(),
                                 hashes.SHA256())
    except (InvalidSignature, binascii.Error, ValueError, TypeError):
        raise NotFromAlexa("signature doesn't match the request")
    check_timestamp(timestamp, now)


def check_timestamp(timestamp, now=None):
    """Step 4: Alexa's timestamps look like 2026-11-01T14:03:12Z."""
    now = now or _now()
    try:
        moment = datetime.fromisoformat(str(timestamp))
    except ValueError:
        raise NotFromAlexa(f"timestamp is malformed: {timestamp!r}")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if abs(now - moment) > MAX_REQUEST_AGE:
        raise NotFromAlexa(f"request is too old or too new: {timestamp}")


def clear_cache():
    with _lock:
        _cache.clear()

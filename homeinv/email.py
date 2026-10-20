"""Outgoing email.

The backend is picked by EMAIL_BACKEND: "mailjet" sends for real, "console"
writes the message to the log (local development), "memory" keeps messages in
a list for tests.
"""

from dataclasses import dataclass
import logging

import requests
from flask import current_app, render_template

log = logging.getLogger(__name__)

MAILJET_SEND_URL = "https://api.mailjet.com/v3.1/send"


@dataclass
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class MailjetBackend:
    def send(self, message):
        config = current_app.config
        payload = {
            "Messages": [
                {
                    "From": {"Email": config["MAIL_FROM_EMAIL"], "Name": config["MAIL_FROM_NAME"]},
                    "To": [{"Email": message.to}],
                    "Subject": message.subject,
                    "TextPart": message.text,
                    "HTMLPart": message.html,
                }
            ]
        }
        response = requests.post(
            MAILJET_SEND_URL,
            json=payload,
            auth=(config["MAILJET_API_KEY"], config["MAILJET_SECRET_KEY"]),
            timeout=10,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Mailjet returned HTTP {response.status_code}: {response.text[:300]}")


class ConsoleBackend:
    def send(self, message):
        log.warning("EMAIL (not sent, console backend)\nTo: %s\nSubject: %s\n\n%s",
                    message.to, message.subject, message.text)


class MemoryBackend:
    def __init__(self):
        self.outbox = []

    def send(self, message):
        self.outbox.append(message)


BACKENDS = {"mailjet": MailjetBackend, "console": ConsoleBackend, "memory": MemoryBackend}


def init_email(app):
    name = app.config["EMAIL_BACKEND"]
    if name not in BACKENDS:
        raise ValueError(f"Unknown EMAIL_BACKEND {name!r}")
    app.extensions["email_backend"] = BACKENDS[name]()


def send_email(to, subject, template, **context):
    """Render templates/email/<template>.txt and .html and send them.

    Returns True if the message was handed off. Failures are logged rather than
    raised, so a mail outage never turns into an error page.
    """
    message = EmailMessage(
        to=to,
        subject=subject,
        text=render_template(f"email/{template}.txt", **context),
        html=render_template(f"email/{template}.html", **context),
    )
    try:
        current_app.extensions["email_backend"].send(message)
        return True
    except Exception:
        log.exception("Sending %r email to %s failed", template, to)
        return False

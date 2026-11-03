"""Transactional mail over Brevo HTTPS; no SMTP socket or provider SDK required."""

import json
import socket
from email.utils import parseaddr
from smtplib import SMTPAuthenticationError, SMTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import validate_email


class HTTPEmailLimitError(SMTPException):
    """The provider rejected a send because its quota or request limit was reached."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An API key must never follow a provider redirect to another origin.
        return None


class BrevoEmailBackend(BaseEmailBackend):
    """Small Django backend for the application's OTP and password-reset mail.

    Supports plain text, HTML, To/Cc/Bcc and one Reply-To. Attachments, custom
    headers and other MIME alternatives are rejected rather than silently lost.
    Provider acceptance is not proof that the recipient's inbox received it.
    """

    endpoint = "https://api.brevo.com/v3/smtp/email"
    max_response_bytes = 65_536
    max_request_bytes = 1_000_000

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        api_key = getattr(settings, "BREVO_API_KEY", "")
        self.api_key = api_key.strip() if isinstance(api_key, str) else ""
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", 15)

    def open(self):
        try:
            if not self.api_key or "\n" in self.api_key or "\r" in self.api_key:
                raise SMTPAuthenticationError(535, b"Brevo API credentials are not configured")
            if not isinstance(self.timeout, (int, float)) or self.timeout <= 0:
                raise SMTPException("Invalid email timeout configuration")
            self.address(settings.DEFAULT_FROM_EMAIL)
        except SMTPException:
            if self.fail_silently:
                return False
            raise
        return True

    def close(self):
        # Each request owns its short-lived HTTPS connection.
        return None

    @staticmethod
    def address(value):
        if not isinstance(value, str) or "\r" in value or "\n" in value:
            raise SMTPException("Invalid email address")
        name, email = parseaddr(value)
        try:
            validate_email(email)
        except ValidationError:
            raise SMTPException("Invalid email address") from None
        return {"email": email, **({"name": name} if name else {})}

    def payload(self, message):
        if message.attachments or message.extra_headers:
            raise SMTPException("Attachments and custom headers are not supported by this backend")
        if not isinstance(message.subject, str) or any(c in message.subject for c in "\r\n"):
            raise SMTPException("Invalid email subject")
        if not isinstance(message.body, str):
            raise SMTPException("Invalid email body")
        if not message.to:
            raise SMTPException("At least one To recipient is required")
        if len(message.reply_to) > 1:
            raise SMTPException("Only one Reply-To address is supported")
        payload = {
            "sender": self.address(message.from_email or settings.DEFAULT_FROM_EMAIL),
            "to": [self.address(value) for value in message.to],
            "subject": message.subject,
        }
        for field in ("cc", "bcc"):
            values = getattr(message, field)
            if values:
                payload[field] = [self.address(value) for value in values]
        if message.reply_to:
            payload["replyTo"] = self.address(message.reply_to[0])
        html = message.body if message.content_subtype == "html" else None
        for alternative in getattr(message, "alternatives", []):
            content, mimetype = alternative
            if mimetype != "text/html" or html is not None or not isinstance(content, str):
                raise SMTPException("Unsupported email alternative")
            html = content
        if message.content_subtype not in ("plain", "html"):
            raise SMTPException("Unsupported email content type")
        # The provider's inline-content API accepts a text or HTML body.
        payload["htmlContent" if html is not None else "textContent"] = (
            html if html is not None else message.body
        )
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(data) > self.max_request_bytes:
            raise SMTPException("Email exceeds the configured request size limit")
        return data

    def send_messages(self, email_messages):
        if not email_messages or not self.open():
            return 0
        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                self.send_message(message)
            except SMTPException:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def send_message(self, message):
        request = Request(
            self.endpoint,
            data=self.payload(message),
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read(self.max_response_bytes + 1)
            if status != 201 or len(raw) > self.max_response_bytes:
                raise SMTPException("Brevo did not confirm message acceptance")
            result = json.loads(raw)
            if not isinstance(result, dict) or not isinstance(result.get("messageId"), str):
                raise SMTPException("Brevo did not confirm message acceptance")
            if not result["messageId"].strip():
                raise SMTPException("Brevo did not confirm message acceptance")
        except HTTPError as exc:
            exc.close()
            # Never propagate the response body: it can contain recipient data.
            if exc.code in (401, 403):
                raise SMTPAuthenticationError(535, b"Brevo API authentication failed") from None
            if exc.code == 429:
                raise HTTPEmailLimitError("Brevo email quota or request limit reached") from None
            raise SMTPException("Brevo rejected the email request") from None
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise SMTPException("Brevo email service is temporarily unavailable") from None
        except (ValueError, TypeError):
            raise SMTPException("Brevo returned an invalid acceptance response") from None

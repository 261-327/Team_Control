"""Mail errors safe to display in either interface."""

from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused, SMTPSenderRefused

from .email_backends import HTTPEmailLimitError


def registration_mail_error(exc):
    if isinstance(exc, HTTPEmailLimitError):
        return "Достигнут лимит отправки писем. Попробуйте позже."
    if isinstance(exc, SMTPAuthenticationError):
        return "Не удалось отправить письмо: почтовый сервис отклонил авторизацию отправителя. Сообщите администратору сайта."
    if isinstance(exc, SMTPRecipientsRefused):
        return "Почтовый сервис отклонил адрес получателя. Проверьте указанную почту или используйте другой адрес."
    if isinstance(exc, SMTPSenderRefused):
        return "Почтовый сервис отклонил отправителя. Сообщите администратору сайта."
    if isinstance(exc, TimeoutError):
        return "Не удалось отправить письмо: почтовый сервис не ответил вовремя. Попробуйте позже."
    return "Не удалось отправить письмо: почтовый сервис временно недоступен. Попробуйте позже."


def mail_failure_details(exc):
    """Bounded diagnostics: never log SMTP text, addresses, links or credentials."""
    code = getattr(exc, "smtp_code", None)
    code = code if isinstance(code, int) and 100 <= code <= 599 else None
    response = getattr(exc, "smtp_error", b"")
    if isinstance(response, bytes):
        response = response[:4096].decode("utf-8", errors="replace")
    response = response.lower() if isinstance(response, str) else ""
    if "spam" in response:
        reason = "spam_policy"
    elif any(word in response for word in ("quota", "limit exceeded", "too many")):
        reason = "quota"
    elif isinstance(exc, SMTPAuthenticationError):
        reason = "authentication"
    elif isinstance(exc, SMTPRecipientsRefused):
        reason = "recipient"
    elif isinstance(exc, SMTPSenderRefused):
        reason = "sender"
    elif code is not None:
        reason = "provider_rejection"
    elif isinstance(exc, (TimeoutError, OSError)):
        reason = "connection"
    else:
        reason = "provider_rejection"
    return code, reason

"""Mail errors safe to display in either interface."""

from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused, SMTPSenderRefused


def registration_mail_error(exc):
    if isinstance(exc, SMTPAuthenticationError):
        return "Не удалось отправить письмо: почтовый сервис отклонил авторизацию отправителя. Сообщите администратору сайта."
    if isinstance(exc, SMTPRecipientsRefused):
        return "Почтовый сервис отклонил адрес получателя. Проверьте указанную почту или используйте другой адрес."
    if isinstance(exc, SMTPSenderRefused):
        return "Почтовый сервис отклонил отправителя. Сообщите администратору сайта."
    if isinstance(exc, TimeoutError):
        return "Не удалось отправить письмо: почтовый сервис не ответил вовремя. Попробуйте позже."
    return "Не удалось отправить письмо: почтовый сервис временно недоступен. Попробуйте позже."

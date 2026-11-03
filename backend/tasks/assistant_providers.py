"""Bounded Workers AI inference; no gateways, paid-model fallback or client secrets.

Cloudflare Workers Free must remain selected on the account. The provider itself
cannot inspect billing-plan changes; its daily allowance stops requests on Free.
"""

import base64
import binascii
import io
import json
import re
import socket
import warnings
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings

TEXT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
TEXT_RESPONSE_LIMIT = 2_000_000
IMAGE_RESPONSE_LIMIT = 8_000_000
IMAGE_BYTES_LIMIT = 5_000_000
IMAGE_PIXELS_LIMIT = 4_194_304


class ProviderUnavailable(Exception):
    """Only a safe, user-facing message may be placed in this exception."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer token to a URL returned by a remote service.
        raise HTTPError(req.full_url, code, "Redirect not allowed", headers, fp)


def _http_open(request, timeout):
    return build_opener(NoRedirect()).open(request, timeout=timeout)


def provider_name():
    return getattr(settings, "ASSISTANT_PROVIDER", "ollama")


def text_model():
    return getattr(settings, "ASSISTANT_CLOUDFLARE_MODEL", TEXT_MODEL)


def image_model():
    return getattr(settings, "ASSISTANT_CLOUDFLARE_IMAGE_MODEL", IMAGE_MODEL)


def configured(*, images=False):
    account = getattr(settings, "CLOUDFLARE_ACCOUNT_ID", "")
    token = getattr(settings, "CLOUDFLARE_API_TOKEN", "")
    return bool(
        isinstance(account, str)
        and re.fullmatch(r"[a-fA-F0-9]{32}", account)
        and isinstance(token, str)
        and token.strip()
        and token.isascii()
        and not any(char.isspace() for char in token)
        and text_model() == TEXT_MODEL
        and (not images or image_model() == IMAGE_MODEL)
    )


def _failure(status):
    if status in (401, 403):
        return "Нет доступа к облачному ИИ. Проверьте настройки Cloudflare на сервере."
    if status in (429, 402):
        return "Лимит облачного ИИ исчерпан или сервис занят. Попробуйте позже."
    return "Облачный ИИ временно недоступен. Попробуйте ещё раз."


def _request(model, payload, *, response_limit):
    if not configured(images=model == IMAGE_MODEL) or model not in (TEXT_MODEL, IMAGE_MODEL):
        raise ProviderUnavailable("Облачный ИИ ещё не настроен на сервере.")
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 300_000:
        raise ProviderUnavailable("Для этого запроса слишком много данных. Выберите один проект.")
    request = Request(
        "https://api.cloudflare.com/client/v4/accounts/"
        + settings.CLOUDFLARE_ACCOUNT_ID
        + "/ai/run/"
        + model,
        data=encoded,
        headers={
            "Authorization": "Bearer " + settings.CLOUDFLARE_API_TOKEN,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with _http_open(request, timeout=settings.ASSISTANT_TIMEOUT) as response:
            raw = response.read(response_limit + 1)
        if len(raw) > response_limit:
            raise ValueError("oversized response")
        envelope = json.loads(raw)
        if not isinstance(envelope, dict):
            raise ValueError("invalid envelope")
        if envelope.get("success") is not True:
            # Do not include vendor messages: they may echo prompts or credentials.
            raise ProviderUnavailable("Облачный ИИ не выполнил запрос. Проверьте лимит и настройки сервиса.")
        result = envelope.get("result")
        if not isinstance(result, dict):
            raise ValueError("invalid result")
        return result
    except HTTPError as exc:
        raise ProviderUnavailable(_failure(exc.code)) from exc
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise ProviderUnavailable("Нет ответа от облачного ИИ. Попробуйте позже.") from exc
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ProviderUnavailable("Облачный ИИ вернул неполный ответ. Попробуйте ещё раз.") from exc


def chat(payload):
    """Adapt our Ollama-shaped internal request and response without changing tools."""
    if not isinstance(payload, dict):
        raise ProviderUnavailable("Не удалось подготовить запрос к облачному ИИ.")
    messages, schema = payload.get("messages"), payload.get("format")
    if not isinstance(messages, list) or not isinstance(schema, dict):
        raise ProviderUnavailable("Не удалось подготовить запрос к облачному ИИ.")
    options = payload.get("options", {})
    result = _request(
        text_model(),
        {
            "messages": messages,
            "stream": False,
            "max_tokens": min(int(options.get("num_predict", 3000)), 4000),
            "temperature": 0.2,
            "response_format": {"type": "json_schema", "json_schema": schema},
        },
        response_limit=TEXT_RESPONSE_LIMIT,
    )
    content = result.get("response")
    if isinstance(content, dict):
        content = json.dumps(content, ensure_ascii=False)
    if not isinstance(content, str) or not content.strip():
        raise ProviderUnavailable("Облачный ИИ вернул пустой ответ. Попробуйте ещё раз.")
    return {
        "message": {"content": content},
        "done_reason": result.get("finish_reason", "stop"),
    }


def generate_image(prompt):
    if not configured(images=True):
        raise ProviderUnavailable("Генерация изображений ещё не настроена на сервере.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ProviderUnavailable("Не удалось подготовить описание изображения.")
    result = _request(
        image_model(),
        {"prompt": prompt[:2048], "steps": 4},
        response_limit=IMAGE_RESPONSE_LIMIT,
    )
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise ProviderUnavailable("На сервере не установлена обработка изображений.") from exc
    try:
        encoded = result.get("image")
        if not isinstance(encoded, str) or len(encoded) > 6_700_000:
            raise ValueError("invalid image field")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > IMAGE_BYTES_LIMIT:
            raise ValueError("oversized image")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("invalid image format")
                if not 0 < source.width * source.height <= IMAGE_PIXELS_LIMIT:
                    raise ValueError("oversized image dimensions")
                source.load()
                output = io.BytesIO()
                source.convert("RGB").save(output, format="PNG", optimize=True)
        png = output.getvalue()
        if len(png) > IMAGE_RESPONSE_LIMIT:
            raise ValueError("oversized PNG")
        return png
    except (
        ValueError,
        TypeError,
        OSError,
        binascii.Error,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ProviderUnavailable("Генератор вернул некорректное изображение. Попробуйте ещё раз.") from exc

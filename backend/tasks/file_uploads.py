"""Shared validation for private project and assistant attachments."""

import io
import os
import zipfile
import uuid
from dataclasses import dataclass

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from django.core.files.base import ContentFile
from django.http import FileResponse

MAX_FILE_BYTES = 3 * 1024 * 1024
MAX_TEXT_CHARS = 12000
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}


class FileUploadError(Exception):
    def __init__(self, message, code="invalid_file", status=400):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass
class ValidatedFile:
    name: str
    content_type: str
    data: bytes

    def content(self):
        return ContentFile(self.data)


def read_docx(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(item.file_size for item in entries) > 20 * 1024 * 1024:
                raise ValueError("oversized document")
            if any(
                item.flag_bits & 1 or item.filename.lower().endswith("vbaproject.bin")
                for item in entries
            ):
                raise ValueError("encrypted or macro-enabled document")
            if archive.getinfo("word/document.xml").file_size > 2 * 1024 * 1024:
                raise ValueError("oversized XML")
            document = archive.read("word/document.xml")
            root = ElementTree.fromstring(document)
            return "\n".join(
                "".join(node.itertext())
                for node in root.iter(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                )
            )[:MAX_TEXT_CHARS]
    except (
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
        DefusedXmlException,
    ) as exc:
        raise FileUploadError(
            "Не удалось прочитать Word. Сохрани документ в формате DOCX и попробуй снова."
        ) from exc


def validate_file(upload):
    if upload is None:
        raise FileUploadError("Выбери файл.")
    if upload.size <= 0:
        raise FileUploadError("Файл пустой.")
    if upload.size > MAX_FILE_BYTES:
        raise FileUploadError("Размер файла должен быть до 3 МБ.", "file_too_large", 413)
    name = upload.name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if ord(char) >= 32 and ord(char) != 127)[:255]
    extension = os.path.splitext(name)[1].lower()
    content_type = ALLOWED_TYPES.get(extension)
    if content_type is None:
        raise FileUploadError(
            "Поддерживаются PDF, DOCX, TXT, MD, CSV, PNG и JPEG.", "unsupported_file_type", 415
        )
    data = upload.read(MAX_FILE_BYTES + 1)
    if len(data) != upload.size or len(data) > MAX_FILE_BYTES:
        raise FileUploadError("Не удалось прочитать файл целиком.")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise FileUploadError("Содержимое файла не соответствует PDF.", status=415)
    if extension in (".png", ".jpg", ".jpeg"):
        # Preserve the private-download format contract. Image analysis decodes and
        # bounds pixels separately before sending anything to a model.
        signature = b"\x89PNG\r\n\x1a\n" if extension == ".png" else b"\xff\xd8\xff"
        if not data.startswith(signature):
            raise FileUploadError("Содержимое файла не соответствует изображению.", status=415)
    if extension == ".docx":
        read_docx(data)
    if extension in (".txt", ".md", ".csv"):
        try:
            text = data.decode("utf-8-sig")
            if "\x00" in text:
                raise ValueError("binary text")
        except (ValueError, UnicodeError) as exc:
            raise FileUploadError("Сохрани текстовый файл в кодировке UTF-8.") from exc
    return ValidatedFile(name or "file" + extension, content_type, data)


def extract_text(file):
    if file.content_type.startswith("image/"):
        return ""
    if file.content_type.endswith("wordprocessingml.document"):
        return read_docx(file.data)
    if file.content_type != "application/pdf":
        return file.data.decode("utf-8-sig")[:MAX_TEXT_CHARS]
    try:
        from pypdf import PdfReader, apply_configuration

        with apply_configuration(
            maximum_declared_stream_length=2 * 1024 * 1024,
            zlib_maximum_output_length=2 * 1024 * 1024,
            lzw_maximum_output_length=2 * 1024 * 1024,
            run_length_maximum_output_length=2 * 1024 * 1024,
            array_based_stream_maximum_output_length=2 * 1024 * 1024,
            stream_decoding_work_maximum_length=4 * 1024 * 1024,
            stream_parsing_work_maximum_count=100000,
            page_tree_maximum_entries=2000,
        ):
            reader = PdfReader(io.BytesIO(file.data), strict=True)
            if reader.is_encrypted:
                raise ValueError("encrypted PDF")
            parts, length = [], 0
            for page in reader.pages[:20]:
                text = page.extract_text() or ""
                parts.append(text[: MAX_TEXT_CHARS - length])
                length += len(parts[-1])
                if length >= MAX_TEXT_CHARS:
                    break
            value = "\n".join(parts).strip()
            if not value:
                raise FileUploadError(
                    "В PDF нет доступного текста. Для скана прикрепи страницу как PNG или JPEG."
                )
            return value
    except FileUploadError:
        raise
    except Exception as exc:
        raise FileUploadError(
            "Не удалось разобрать PDF. Попробуй DOCX, текстовый файл или изображение страницы."
        ) from exc


def download_file(file, name):
    response = FileResponse(
        file.open("rb"),
        as_attachment=True,
        filename=name or "download",
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def validate_image(raw):
    import warnings
    from PIL import Image

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ("PNG", "JPEG") or image.width * image.height > 16_777_216:
                    raise ValueError("image bounds")
                image.verify()
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise FileUploadError("Прикрепи корректный PNG или JPEG до 16 мегапикселей.") from exc


def upload_request_id(data):
    try:
        return uuid.UUID(str(data["requestId"])) if data.get("requestId") else uuid.uuid4()
    except (ValueError, TypeError, AttributeError) as exc:
        raise FileUploadError("Некорректный номер загрузки.") from exc

"""Atomic comment/file upload using existing private storage and validation."""
import hashlib
import json
import os
import uuid
from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from .api import endpoint, APIError, text, project_for, notify_comment, require_rate
from .file_uploads import validate_file, upload_request_id, download_file
from .models import Task, Comment, CommentAttachment
from .serializers import snapshot


@endpoint(("POST",), multipart=True)
def send_comment(request, task_id):
    if not settings.PROJECT_FILE_UPLOADS_ENABLED:
        raise APIError("Постоянное хранилище файлов ещё не настроено.", "storage_unavailable", 503)
    require_rate('comment-file', (request.user.pk,), 40, 3600, 'Слишком много загрузок. Попробуйте позже.')
    message = text(request.data, 'text', 2000, True)
    if not request.data.get('requestId'):
        raise APIError('Укажите номер отправки сообщения.')
    request_id = upload_request_id(request.data)
    uploaded = validate_file(request.FILES.get('file'))
    fingerprint = hashlib.sha256(json.dumps([message, uploaded.name, uploaded.content_type],ensure_ascii=False).encode()+b'\0'+uploaded.data).hexdigest()
    attachment = None
    try:
        with transaction.atomic():
            task = get_object_or_404(Task.objects.select_related('column__board'), pk=task_id)
            project = project_for(request.user, task.column.board.project_id, lock=True)
            previous = Comment.objects.filter(upload_request_id=request_id).first()
            if previous:
                if previous.task_id != task.pk or previous.user_id != request.user.pk:
                    raise Http404
                if previous.upload_fingerprint != fingerprint:
                    raise APIError('Содержимое повторного запроса изменилось.', 'conflict', 409)
                return {'commentId': str(previous.pk), 'snapshot': snapshot(request)}
            comment = Comment.objects.create(task=task,user=request.user,text=message,upload_request_id=request_id,upload_fingerprint=fingerprint)
            attachment = CommentAttachment(comment=comment,original_filename=uploaded.name,file_size=len(uploaded.data),content_type=uploaded.content_type)
            attachment.file.save(uuid.uuid4().hex+os.path.splitext(uploaded.name)[1].lower(),uploaded.content(),save=False)
            attachment.save()
            notify_comment(project,task,comment,request.user)
    except Exception:
        if attachment and attachment.file and attachment.file._committed:
            attachment.file.delete(save=False)
        raise
    return {'commentId': str(comment.pk), 'snapshot': snapshot(request)}


@endpoint()
def download(request, attachment_id):
    attachment = get_object_or_404(CommentAttachment.objects.select_related('comment__task__column__board'), pk=attachment_id)
    project_for(request.user,attachment.comment.task.column.board.project_id)
    try:
        return download_file(attachment.file,attachment.original_filename)
    except (OSError, ValueError):
        raise Http404 from None

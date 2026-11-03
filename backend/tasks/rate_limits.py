"""Atomic PostgreSQL/SQLite rate limits shared by every web process.

No cache fallback is safe here: a database failure closes the protected endpoint.
All keys use an application-secret HMAC, including email and network identities.
"""

import ipaddress
import json
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, connection
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import RateLimitCounter


class RateLimitUnavailable(Exception):
    pass


_cleanup_lock = threading.Lock()
_next_cleanup = 0.0
CLEANUP_BATCH = 128


def client_identity(request):
    # Only the private Services caller may supply this overwritten header. Generic
    # X-Forwarded-For is never trusted, including local/Render deployments.
    if getattr(settings, "SIPI_VERCEL_SERVICES", False):
        raw = request.META.get("HTTP_X_SIPI_CLIENT_IP", "")
    else:
        raw = request.META.get("REMOTE_ADDR", "")
    try:
        if not isinstance(raw, str) or "%" in raw or len(raw) > 45:
            raise ValueError
        address = ipaddress.ip_address(raw.strip())
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.compressed
    except ValueError:
        # Missing identity shares a conservative bucket rather than bypassing a limit.
        return "unknown-peer"


def counter_key(scope, *identity):
    value = json.dumps([scope, *identity], ensure_ascii=True, separators=(",", ":"))
    return salted_hmac("sipi.auth.rate-limits.v1", value, algorithm="sha256").hexdigest()


def cleanup_expired(now):
    table = connection.ops.quote_name(RateLimitCounter._meta.db_table)
    expiry = RateLimitCounter._meta.get_field("expires_at").get_db_prep_value(now, connection)
    with connection.cursor() as cursor:
        # One bounded statement; a renewed row cannot be removed by an older snapshot.
        cursor.execute(
            f'DELETE FROM {table} WHERE "key" IN '
            f'(SELECT "key" FROM {table} WHERE "expires_at" <= %s '
            'ORDER BY "expires_at" LIMIT %s) AND "expires_at" <= %s',
            [expiry, CLEANUP_BATCH, expiry],
        )
        return cursor.rowcount


def _maybe_cleanup(now):
    global _next_cleanup
    current = time.monotonic()
    if current < _next_cleanup:
        return
    with _cleanup_lock:
        if current < _next_cleanup:
            return
        _next_cleanup = current + 60
    cleanup_expired(now)


def consume(scope, identity, limit, seconds):
    """Reserve one attempt without extending a full window; returns False when full.

    A single conditional UPSERT handles first use, expiry and concurrent requests.
    PostgreSQL and Django-supported modern SQLite both support this syntax. It
    needs no process-local lock, read/check/increment race or persistent worker.
    """
    key = counter_key(scope, *identity)
    now = timezone.now()
    field = RateLimitCounter._meta.get_field("expires_at")
    current = field.get_db_prep_value(now, connection)
    expiry = field.get_db_prep_value(now + timedelta(seconds=seconds), connection)
    table = connection.ops.quote_name(RateLimitCounter._meta.db_table)
    query = (
        f'INSERT INTO {table} ("key", "count", "expires_at") VALUES (%s, 1, %s) '
        'ON CONFLICT ("key") DO UPDATE SET '
        f'"count" = CASE WHEN {table}."expires_at" <= %s THEN 1 '
        f'ELSE {table}."count" + 1 END, '
        f'"expires_at" = CASE WHEN {table}."expires_at" <= %s THEN %s '
        f'ELSE {table}."expires_at" END '
        f'WHERE {table}."expires_at" <= %s OR {table}."count" < %s'
    )
    for attempt in range(4):
        try:
            _maybe_cleanup(now)
            with connection.cursor() as cursor:
                cursor.execute(query, [key, expiry, current, current, expiry, current, limit])
                return cursor.rowcount == 1
        except DatabaseError as exc:
            # Shared-cache SQLite may fail immediately on concurrent writers. The
            # statement is atomic; a brief bounded retry does not grant extra attempts.
            retry = (
                connection.vendor == "sqlite"
                and not connection.in_atomic_block
                and any(word in str(exc).lower() for word in ("locked", "busy"))
                and attempt < 3
            )
            if not retry:
                raise RateLimitUnavailable from None
            time.sleep(0.01 * (attempt + 1))
    raise RateLimitUnavailable


def clear(scope, *identity):
    try:
        RateLimitCounter.objects.filter(key=counter_key(scope, *identity)).delete()
    except DatabaseError:
        raise RateLimitUnavailable from None

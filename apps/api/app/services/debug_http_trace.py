from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from typing import Any, BinaryIO
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from app.schemas.runs import DebugHttpTrace, DebugHttpTraceBody, DebugHttpTraceEntry

DEBUG_HTTP_TRACE_ARTIFACT_TYPE = "debug_http_trace"
DEBUG_HTTP_BODY_BLOB_ARTIFACT_TYPE = "debug_http_body_blob"
DEBUG_HTTP_TRACE_RELATIVE_PATH = "artifacts/debug-http-trace.jsonl"
REDACTED = "[REDACTED]"
SENSITIVE_NAME = re.compile(
    r"authorization|cookie|set-cookie|x-api-key|token|password|secret|key", re.I
)
SENSITIVE_VALUE_PATTERN = r"[^\s,;&}\]\[\"'<>]+"
TEXT_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/x-www-form-urlencoded",
)
MAX_NESTED_URL_DECODE_DEPTH = 3


def is_sensitive_name(name: object) -> bool:
    return isinstance(name, str) and SENSITIVE_NAME.search(name) is not None


def sanitize_headers(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key)[:200]
        result[name] = (
            REDACTED
            if is_sensitive_name(name)
            else (sanitize_free_text(value, max_length=8192) or "")
        )
    return result


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (REDACTED if is_sensitive_name(key) else _sanitize_json(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, str):
        return _sanitize_body_string_value(value)
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)


def _sanitize_body_string_value(value: str) -> str:
    return sanitize_free_text(value, max_length=max(len(value) * 4, len(value) + 1024, 4096)) or ""


def _is_urlish_or_sensitive_assignment(value: str) -> bool:
    return (
        "://" in value
        or "?" in value
        or "#" in value
        or re.search(r"(?i)(token|password|secret|key)[^=&\s]*=", value) is not None
    )


def _decode_nested_urlish_or_sensitive_value(value: str) -> str | None:
    current = value
    for _ in range(MAX_NESTED_URL_DECODE_DEPTH):
        if "%" not in current:
            return (
                current
                if current != value and _is_urlish_or_sensitive_assignment(current)
                else None
            )
        try:
            decoded = unquote(current)
        except ValueError:
            return None
        if decoded == current:
            return (
                current
                if current != value and _is_urlish_or_sensitive_assignment(current)
                else None
            )
        current = decoded
        if _is_urlish_or_sensitive_assignment(current):
            return current
    return current if current != value and _is_urlish_or_sensitive_assignment(current) else None


def _sanitize_url_component_value(value: str, *, depth: int) -> str:
    decoded = _decode_nested_urlish_or_sensitive_value(value) or value
    if depth < MAX_NESTED_URL_DECODE_DEPTH and (
        "://" in decoded or "?" in decoded or "#" in decoded
    ):
        return sanitize_url(decoded, _depth=depth + 1)
    if re.search(r"(?i)(token|password|secret|key)[^=&\s]*=", decoded):
        return sanitize_free_text(decoded, max_length=4096) or ""
    return decoded


def sanitize_url(raw: Any, *, _depth: int = 0) -> str:
    url = str(raw or "")[:4096]
    try:
        parsed = urlsplit(url)
    except ValueError:
        return re.sub(
            r"(?i)([?&][^=&]*(?:token|password|secret|key)[^=&]*=)[^&#]*",
            rf"\1{REDACTED}",
            re.sub(r"://[^/@]+@", f"://{REDACTED}@", url),
        )
    query = urlencode(
        [
            (
                key,
                REDACTED
                if is_sensitive_name(key)
                else _sanitize_url_component_value(value, depth=_depth),
            )
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    netloc = parsed.netloc
    if "@" in netloc:
        netloc = f"{REDACTED}@{netloc.rsplit('@', 1)[1]}"
    fragment = parsed.fragment
    if "=" in fragment:
        fragment = urlencode(
            [
                (
                    key,
                    REDACTED
                    if is_sensitive_name(key)
                    else _sanitize_url_component_value(value, depth=_depth),
                )
                for key, value in parse_qsl(fragment, keep_blank_values=True)
            ]
        )
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, fragment))[:4096]


def _sanitize_body_text(text: str, content_type: str | None) -> str:
    lowered = (content_type or "").lower()
    stripped = text.strip()
    if "json" in lowered or stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return sanitize_free_text(text, max_length=max(len(text) * 4, len(text) + 1024)) or ""
        return json.dumps(_sanitize_json(parsed), ensure_ascii=False, separators=(",", ":"))
    if "x-www-form-urlencoded" in lowered or (not lowered and "=" in text and "\n" not in text):
        pairs = []
        for key, value in parse_qsl(text, keep_blank_values=True):
            pairs.append(
                (key, REDACTED if is_sensitive_name(key) else _sanitize_body_string_value(value))
            )
        return urlencode(pairs)
    return sanitize_free_text(text, max_length=max(len(text) * 4, len(text) + 1024)) or text


def sanitize_free_text(raw: Any, *, max_length: int) -> str | None:
    if raw is None:
        return None
    text = str(raw)
    decoded = _decode_nested_urlish_or_sensitive_value(text)
    if decoded is not None:
        text = decoded
    return _sanitize_free_text_patterns(text, max_length=max_length)


def _sanitize_free_text_patterns(raw: Any, *, max_length: int) -> str | None:
    if raw is None:
        return None
    text = str(raw)

    def replace_url(match: re.Match[str]) -> str:
        return sanitize_url(match.group(0))

    text = re.sub(r"https?://[^\s\"'<>]+", replace_url, text)
    text = re.sub(
        r"(?i)\b(authorization|x-api-key)\s*[:=]\s*(?:bearer|basic|digest)?\s*"
        + SENSITIVE_VALUE_PATTERN,
        lambda match: f"{match.group(1)}: {REDACTED}",
        text,
    )
    text = re.sub(
        r"(?i)\b((?:cookie|set-cookie)\s*[:=]\s*)([^\r\n]*)",
        lambda match: (
            match.group(1) + re.sub(r"([^=;\s,]+)=([^;,\s]+)", rf"\1={REDACTED}", match.group(2))
        ),
        text,
    )
    text = re.sub(
        (
            r"(?is)(<\s*([A-Za-z0-9_.:-]*(?:token|password|secret|key)"
            r"[A-Za-z0-9_.:-]*)\b[^>]*>).*?(</\s*\2\s*>)"
        ),
        rf"\1{REDACTED}\3",
        text,
    )
    text = re.sub(
        r"(?i)\b(bearer|basic|digest)\s+" + SENSITIVE_VALUE_PATTERN,
        rf"\1 {REDACTED}",
        text,
    )
    text = re.sub(
        (
            r"(?i)([\"']?\b[A-Za-z0-9_.-]*(?:token|password|secret|key)"
            r"[A-Za-z0-9_.-]*[\"']?\s*(?::|=|\bis\b)\s*[\"'])"
            r".*?([\"'])"
        ),
        rf"\1{REDACTED}\2",
        text,
    )
    text = re.sub(
        (
            r"(?i)([\"']?\b[A-Za-z0-9_.-]*(?:token|password|secret|key)"
            r"[A-Za-z0-9_.-]*[\"']?\s*(?::|=|\bis\b)\s*)"
            r"([\"']?)" + SENSITIVE_VALUE_PATTERN + r"([\"']?)"
        ),
        rf"\1\2{REDACTED}\3",
        text,
    )
    text = re.sub(
        (
            r"(?i)(\b[A-Za-z0-9_.-]*(?:token|password|secret|key)"
            r"[A-Za-z0-9_.-]*\s+)" + SENSITIVE_VALUE_PATTERN
        ),
        rf"\1{REDACTED}",
        text,
    )
    return text[:max_length] or None


def _looks_previewable_text(text: str) -> bool:
    if text == "":
        return True
    if "\ufffd" in text:
        return False
    control_count = sum(
        1
        for char in text
        if (
            (ord(char) < 32 and char not in {"\t", "\n", "\r"})
            or ord(char) == 127
            or 128 <= ord(char) <= 159
            or unicodedata.category(char) == "Cc"
        )
    )
    return control_count == 0


def _is_textual(content_type: str | None, text: str | None = None) -> bool:
    lowered = (content_type or "").lower()
    if not lowered:
        return _looks_previewable_text(text or "")
    return lowered.startswith(TEXT_CONTENT_TYPES) or "json" in lowered or "xml" in lowered


def _metadata_body(
    raw: dict[str, Any], *, content_type: str | None, text: str, drop_reason: str = "binary_body"
) -> DebugHttpTraceBody:
    data = text.encode("utf-8", errors="replace")
    raw_sha = raw.get("sha256Prefix")
    sha = (
        str(raw_sha)[:16]
        if isinstance(raw_sha, str) and re.fullmatch(r"[0-9a-fA-F]{1,64}", raw_sha)
        else (hashlib.sha256(data).hexdigest()[:16] if data else None)
    )
    size = raw.get("sizeBytes") if isinstance(raw.get("sizeBytes"), int) else len(data)
    return DebugHttpTraceBody(
        content_type=content_type,
        body_storage="dropped",
        body_truncated=False,
        size_bytes=size,
        sha256_prefix=sha,
        drop_reason=drop_reason,
    )


def _safe_sha(raw: Any) -> str | None:
    return (
        str(raw)[:16] if isinstance(raw, str) and re.fullmatch(r"[0-9a-fA-F]{1,64}", raw) else None
    )


def sanitize_body(
    raw: Any,
    *,
    body_max_bytes: int,
    body_blob_artifact_ids_by_relative_path: dict[str, str] | None = None,
) -> DebugHttpTraceBody:
    if not isinstance(raw, dict):
        return DebugHttpTraceBody(
            content_type=None,
            text="",
            inline_preview="",
            body_storage="inline",
            body_truncated=False,
        )
    content_type = raw.get("contentType") if isinstance(raw.get("contentType"), str) else None
    text = str(raw.get("text") or "")
    raw_storage = raw.get("bodyStorage")
    body_storage = (
        raw_storage if raw_storage in {"inline", "truncated", "sidecar", "dropped"} else None
    )
    raw_size = raw.get("sizeBytes") if isinstance(raw.get("sizeBytes"), int) else None
    sha = _safe_sha(raw.get("sha256Prefix"))
    if body_storage == "dropped":
        return DebugHttpTraceBody(
            content_type=content_type,
            body_storage="dropped",
            body_truncated=raw.get("bodyTruncated") is True,
            size_bytes=raw_size,
            sha256_prefix=sha,
            drop_reason=str(raw.get("dropReason") or "body_dropped")[:100],
        )
    if body_storage == "sidecar":
        preview = _sanitize_body_text(text, content_type) if text else None
        relative_path = (
            raw.get("downloadRelativePath")
            if isinstance(raw.get("downloadRelativePath"), str)
            else None
        )
        artifact_id = (
            (body_blob_artifact_ids_by_relative_path or {}).get(relative_path)
            if relative_path
            else None
        )
        if artifact_id is None:
            return DebugHttpTraceBody(
                content_type=content_type,
                body_storage="dropped",
                body_truncated=True,
                size_bytes=raw_size,
                sha256_prefix=sha,
                drop_reason="sidecar_missing",
            )
        return DebugHttpTraceBody(
            content_type=content_type,
            text=preview,
            inline_preview=preview,
            body_storage="sidecar",
            body_truncated=True,
            size_bytes=raw_size,
            sha256_prefix=sha,
            download_artifact_id=artifact_id,
            download_relative_path=None,
        )
    if (
        not text
        and content_type is None
        and (isinstance(raw.get("sizeBytes"), int) or isinstance(raw.get("sha256Prefix"), str))
    ):
        return _metadata_body(raw, content_type=content_type, text=text)
    if not _is_textual(content_type, text):
        return _metadata_body(raw, content_type=content_type, text=text)
    text = _sanitize_body_text(text, content_type)
    encoded = text.encode("utf-8", errors="replace")
    truncated = False
    storage = "inline"
    if len(encoded) > body_max_bytes:
        truncated = True
        storage = "truncated"
        text = encoded[:body_max_bytes].decode("utf-8", errors="ignore")
    if raw.get("bodyTruncated") is True:
        truncated = True
        if storage == "inline":
            storage = "truncated"
    return DebugHttpTraceBody(
        content_type=content_type,
        text=text,
        inline_preview=text,
        body_storage=storage,  # type: ignore[arg-type]
        body_truncated=truncated,
        size_bytes=raw_size if raw_size is not None else len(encoded),
        sha256_prefix=sha,
    )


def _safe_int(raw: Any) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return int(value)


def _entry(
    raw: dict[str, Any],
    *,
    body_max_bytes: int,
    body_blob_artifact_ids_by_relative_path: dict[str, str] | None = None,
) -> DebugHttpTraceEntry:
    return DebugHttpTraceEntry(
        sequence=_safe_int(raw.get("sequence")) or 0,
        label=sanitize_free_text(raw.get("label"), max_length=300),
        method=str(raw.get("method") or "GET").upper()[:20],
        url=sanitize_url(raw.get("url")),
        request_headers=sanitize_headers(raw.get("requestHeaders")),
        request_body=sanitize_body(
            raw.get("requestBody"),
            body_max_bytes=body_max_bytes,
            body_blob_artifact_ids_by_relative_path=body_blob_artifact_ids_by_relative_path,
        ),
        response_status=_safe_int(raw.get("responseStatus")),
        response_headers=sanitize_headers(raw.get("responseHeaders")),
        response_body=sanitize_body(
            raw.get("responseBody"),
            body_max_bytes=body_max_bytes,
            body_blob_artifact_ids_by_relative_path=body_blob_artifact_ids_by_relative_path,
        ),
        duration_ms=_safe_int(raw.get("durationMs")),
        error=sanitize_free_text(raw.get("error"), max_length=1000),
    )


def parse_debug_http_trace_jsonl(
    stream: BinaryIO,
    *,
    source_artifact_id: str,
    max_requests: int,
    body_max_bytes: int,
    artifact_max_bytes: int,
    record_max_bytes: int = 128 * 1024,
    body_blob_artifact_ids_by_relative_path: dict[str, str] | None = None,
) -> DebugHttpTrace:
    entries: list[DebugHttpTraceEntry] = []
    warnings: set[str] = set()
    trace_truncated = False
    saw_nonempty_line = False
    total_read = 0
    first_line = True
    while True:
        data_line = stream.readline(record_max_bytes + 2)
        if not data_line:
            break
        total_read += len(data_line)
        if total_read > artifact_max_bytes:
            return DebugHttpTrace(
                status="unavailable",
                source_artifact_id=source_artifact_id,
                entry_count=0,
                trace_truncated=True,
                warnings=["debug_http_trace_too_large"],
                entries=[],
            )
        if len(data_line) > record_max_bytes:
            warnings.add("debug_http_trace_line_too_large")
            while data_line and not data_line.endswith(b"\n"):
                data_line = stream.readline(8192)
                total_read += len(data_line)
                if total_read > artifact_max_bytes:
                    return DebugHttpTrace(
                        status="unavailable",
                        source_artifact_id=source_artifact_id,
                        entry_count=0,
                        trace_truncated=True,
                        warnings=["debug_http_trace_too_large"],
                        entries=[],
                    )
            continue
        try:
            line = data_line.decode("utf-8-sig" if first_line else "utf-8")
        except UnicodeDecodeError:
            warnings.add("debug_http_trace_decode_failed")
            first_line = False
            continue
        first_line = False
        if not line.strip():
            continue
        saw_nonempty_line = True
        if len(entries) >= max_requests:
            trace_truncated = True
            break
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            warnings.add("debug_http_trace_line_parse_failed")
            continue
        if not isinstance(raw, dict):
            warnings.add("debug_http_trace_line_invalid")
            continue
        if raw.get("traceTruncated") is True and "url" not in raw and "method" not in raw:
            trace_truncated = True
            continue
        entries.append(
            _entry(
                raw,
                body_max_bytes=body_max_bytes,
                body_blob_artifact_ids_by_relative_path=body_blob_artifact_ids_by_relative_path,
            )
        )
        if raw.get("traceTruncated") is True:
            trace_truncated = True
    if saw_nonempty_line and not entries and warnings:
        return DebugHttpTrace(
            status="unavailable",
            source_artifact_id=source_artifact_id,
            entry_count=0,
            trace_truncated=trace_truncated,
            warnings=sorted(warnings),
            entries=[],
        )
    return DebugHttpTrace(
        status="available",
        source_artifact_id=source_artifact_id,
        entry_count=len(entries),
        trace_truncated=trace_truncated,
        warnings=sorted(warnings),
        entries=entries,
    )


DEBUG_HTTP_TRACE_JSR223_SCRIPT_TEMPLATE = r"""
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import java.net.URI
import java.net.URLDecoder
import java.net.URLEncoder
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

File out = new File('artifacts/debug-http-trace.jsonl')
out.parentFile.mkdirs()
int maxRequests = __MAX_REQUESTS__
int bodyMaxBytes = __BODY_MAX_BYTES__
int recordMaxBytes = __RECORD_MAX_BYTES__
int bodyBlobMaxBytes = __BODY_BLOB_MAX_BYTES__
long bodyBlobTotalMaxBytes = __BODY_BLOB_TOTAL_MAX_BYTES__L
long artifactMaxBytes = __ARTIFACT_MAX_BYTES__L
File bodyBlobDir = new File('artifacts/debug-http-body-blobs')
long bodyBlobBytesWritten = (vars.getObject('lpDebugTraceBodyBlobBytesWritten') ?: 0L) as long
def redactName = { name ->
  def lowered = String.valueOf(name ?: '').toLowerCase(Locale.ROOT)
  return lowered == 'authorization' || lowered == 'cookie' || lowered == 'set-cookie' || lowered == 'x-api-key' || lowered.contains('token') || lowered.contains('password') || lowered.contains('secret') || lowered.contains('key')
}
def redactJson
def sanitizeStringValue
redactJson = { value ->
  if (value instanceof Map) {
    def result = [:]
    value.each { key, item ->
      result[String.valueOf(key)] = redactName(key) ? '[REDACTED]' : redactJson(item)
    }
    return result
  }
  if (value instanceof List) {
    return value.collect { item -> redactJson(item) }
  }
  if (value instanceof CharSequence) {
    return sanitizeStringValue(value)
  }
  return value
}
def sanitizeUrl
def redactTextFallback = { value ->
  def raw = String.valueOf(value ?: '')
  raw = raw.replaceAll(/https?:\/\/[^\s"'<>]+/) { match -> sanitizeUrl(match[0]) }
  raw = raw.replaceAll(/(?i)\b(authorization|x-api-key)\s*[:=]\s*(?:bearer|basic|digest)?\s*[^\s,;&}\]\["'<>]+/, '$1: [REDACTED]')
  raw = raw.replaceAll(/(?i)\b((?:cookie|set-cookie)\s*[:=]\s*)([^\r\n]*)/) { all, prefix, valueText ->
    return prefix + String.valueOf(valueText).replaceAll(/([^=;\s,]+)=([^;,\s]+)/, '$1=[REDACTED]')
  }
  raw = raw.replaceAll(/(?i)\b(bearer|basic|digest)\s+[^\s,;&}\]\["'<>]+/, '$1 [REDACTED]')
  raw = raw.replaceAll(/(?is)(<\s*([A-Za-z0-9_.:-]*(?:token|password|secret|key)[A-Za-z0-9_.:-]*)\b[^>]*>).*?(<\/\s*\2\s*>)/, '$1[REDACTED]$3')
  raw = raw.replaceAll(/(?i)(["']?\b[A-Za-z0-9_.-]*(?:token|password|secret|key)[A-Za-z0-9_.-]*["']?\s*(?::|=|\bis\b)\s*["']).*?(["'])/, '$1[REDACTED]$2')
  raw = raw.replaceAll(/(?i)(["']?\b[A-Za-z0-9_.-]*(?:token|password|secret|key)[A-Za-z0-9_.-]*["']?\s*(?::|=|\bis\b)\s*)(["']?)[^\s,;&}\]\["'<>]+(["']?)/, '$1$2[REDACTED]$3')
  return raw.replaceAll(/(?i)(\b[A-Za-z0-9_.-]*(?:token|password|secret|key)[A-Za-z0-9_.-]*\s+)[^\s,;&}\]\["'<>]+/, '$1[REDACTED]')
}
sanitizeStringValue = { value ->
  def raw = String.valueOf(value ?: '')
  def sanitized = redactTextFallback(raw)
  def decoded = raw
  boolean foundNestedSensitive = false
  for (int decodeDepth = 0; decodeDepth < 3; decodeDepth++) {
    if (!decoded.contains('%')) {
      break
    }
    def nextDecoded = decoded
    try { nextDecoded = URLDecoder.decode(decoded, 'UTF-8') } catch (Throwable ignored) { break }
    if (nextDecoded == decoded) {
      break
    }
    decoded = nextDecoded
    if (decoded.contains('://') || decoded.contains('?') || decoded.contains('#') || (decoded =~ /(?i)(token|password|secret|key)[^=&\s]*=/)) {
      foundNestedSensitive = true
      break
    }
  }
  return foundNestedSensitive ? redactTextFallback(decoded) : sanitized
}
def sanitizeBodyText = { contentType, text ->
  def raw = String.valueOf(text ?: '')
  def lowered = String.valueOf(contentType ?: '').toLowerCase(Locale.ROOT)
  def trimmed = raw.trim()
  if (lowered.contains('json') || trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      return JsonOutput.toJson(redactJson(new JsonSlurper().parseText(raw)))
    } catch (Throwable ignored) {
      return sanitizeStringValue(raw)
    }
  }
  if (lowered.contains('x-www-form-urlencoded') || (raw.contains('=') && !raw.contains('\\n'))) {
    return raw.split('&').collect { part ->
      int idx = part.indexOf('=')
      if (idx < 0) {
        return part
      }
      def key = URLDecoder.decode(part.substring(0, idx), 'UTF-8')
      def value = URLDecoder.decode(part.substring(idx + 1), 'UTF-8')
      def safeValue = URLEncoder.encode(redactName(key) ? '[REDACTED]' : sanitizeStringValue(value), 'UTF-8')
      return part.substring(0, idx) + '=' + safeValue
    }.join('&')
  }
  return sanitizeStringValue(raw)
}
def isTextual = { contentType ->
  def lowered = String.valueOf(contentType ?: '').toLowerCase(Locale.ROOT)
  return lowered.startsWith('text/') || lowered.contains('json') || lowered.contains('xml') || lowered.contains('x-www-form-urlencoded')
}
def bytesForPayload = { payload ->
  return payload instanceof byte[] ? payload : String.valueOf(payload ?: '').getBytes('UTF-8')
}
def looksPreviewableBytes = { bytes ->
  if (bytes.length == 0) {
    return true
  }
  try {
    def decoder = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
    decoder.decode(ByteBuffer.wrap(bytes))
  } catch (Throwable ignored) {
    return false
  }
  for (byte rawByte : bytes) {
    int value = rawByte & 0xFF
    if ((value < 32 && value != 9 && value != 10 && value != 13) || value == 127 || (value >= 128 && value <= 159)) {
      return false
    }
  }
  return true
}
def shouldPreviewBody = { contentType, payload ->
  def lowered = String.valueOf(contentType ?: '').toLowerCase(Locale.ROOT)
  if (lowered != '') {
    return isTextual(contentType)
  }
  return looksPreviewableBytes(bytesForPayload(payload))
}
def sanitizeUrlComponentValue = { value, depth ->
  def decoded = String.valueOf(value ?: '')
  for (int decodeDepth = 0; decodeDepth < 3; decodeDepth++) {
    if (!decoded.contains('%')) {
      break
    }
    def nextDecoded = decoded
    try { nextDecoded = URLDecoder.decode(decoded, 'UTF-8') } catch (Throwable ignored) { break }
    if (nextDecoded == decoded) {
      break
    }
    decoded = nextDecoded
    if (decoded.contains('://') || decoded.contains('?') || decoded.contains('#') || (decoded =~ /(?i)(token|password|secret|key)[^=&\s]*=/)) {
      break
    }
  }
  if (depth < 3 && (decoded.contains('://') || decoded.contains('?') || decoded.contains('#'))) {
    return sanitizeUrl(decoded, depth + 1)
  }
  return redactTextFallback(decoded)
}
sanitizeUrl = { value, depth = 0 ->
  def raw = String.valueOf(value ?: '')
  try {
    def uri = new URI(raw)
    def query = uri.getRawQuery()
    def safeQuery = query == null ? null : query.split('&').collect { part ->
      int idx = part.indexOf('=')
      if (idx < 0) {
        return part
      }
      def key = URLDecoder.decode(part.substring(0, idx), 'UTF-8')
      def safeValue = redactName(key) ? URLEncoder.encode('[REDACTED]', 'UTF-8') : URLEncoder.encode(sanitizeUrlComponentValue(part.substring(idx + 1), depth), 'UTF-8')
      return part.substring(0, idx) + '=' + safeValue
    }.join('&')
    def authority = uri.getRawAuthority()
    if (authority != null && authority.contains('@')) {
      authority = '[REDACTED]@' + authority.substring(authority.indexOf('@') + 1)
    }
    def fragment = uri.getRawFragment()
    if (fragment != null && fragment.contains('=')) {
      fragment = fragment.split('&').collect { part ->
        int idx = part.indexOf('=')
        if (idx < 0) {
          return part
        }
        def key = URLDecoder.decode(part.substring(0, idx), 'UTF-8')
        def safeValue = redactName(key) ? URLEncoder.encode('[REDACTED]', 'UTF-8') : URLEncoder.encode(sanitizeUrlComponentValue(part.substring(idx + 1), depth), 'UTF-8')
        return part.substring(0, idx) + '=' + safeValue
      }.join('&')
    }
    def result = new StringBuilder()
    if (uri.getScheme() != null) { result << uri.getScheme() << ':' }
    if (authority != null) { result << '//' << authority }
    if (uri.getRawPath() != null) { result << uri.getRawPath() }
    if (safeQuery != null) { result << '?' << safeQuery }
    if (fragment != null) { result << '#' << fragment }
    return result.toString()
  } catch (Throwable ignored) {
    return raw.replaceFirst('://[^/@]+@', '://[REDACTED]@').replaceAll('(?i)([?&#][^=&]*(token|password|secret|key)[^=&]*=)[^&#]*', '$1[REDACTED]')
  }
}
def sanitizeFreeText = { value ->
  def raw = String.valueOf(value ?: '')
  return sanitizeStringValue(raw)
}
def redactHeaders = { text ->
  def result = [:]
  String.valueOf(text ?: '').split('\\r?\\n').each { line ->
    int idx = line.indexOf(':')
    if (idx > 0) {
      def key = line.substring(0, idx).trim()
      def value = line.substring(idx + 1).trim()
      result[key] = redactName(key) ? '[REDACTED]' : sanitizeFreeText(value)
    }
  }
  return result
}
def sha256Prefix = { bytes ->
  MessageDigest.getInstance('SHA-256').digest(bytes).encodeHex().toString().substring(0, 16)
}
def previewText = { text ->
  byte[] safeBytes = String.valueOf(text ?: '').getBytes('UTF-8')
  return safeBytes.length > bodyMaxBytes ? new String(safeBytes[0..<bodyMaxBytes] as byte[], 'UTF-8') : String.valueOf(text ?: '')
}
def droppedBody = { contentType, bytes, reason ->
  return [
    contentType: contentType,
    bodyStorage: 'dropped',
    bodyTruncated: false,
    sizeBytes: bytes.length,
    sha256Prefix: sha256Prefix(bytes),
    dropReason: reason
  ]
}
def sidecarBody = { contentType, bytes, seq, bodyKind ->
  if (bytes.length > bodyBlobMaxBytes) {
    return droppedBody(contentType, bytes, 'body_too_large')
  }
  def text = new String(bytes, 'UTF-8')
  def safeFull = sanitizeStringValue(text)
  byte[] safeBytes = safeFull.getBytes('UTF-8')
  if (safeBytes.length > bodyBlobMaxBytes) {
    return droppedBody(contentType, bytes, 'body_too_large')
  }
  if (bodyBlobBytesWritten + safeBytes.length > bodyBlobTotalMaxBytes) {
    return droppedBody(contentType, bytes, 'sidecar_budget_exceeded')
  }
  bodyBlobDir.mkdirs()
  def fileName = String.valueOf(seq) + '-' + String.valueOf(bodyKind) + '.bin'
  def blobFile = new File(bodyBlobDir, fileName)
  blobFile.bytes = safeBytes
  bodyBlobBytesWritten += safeBytes.length
  vars.putObject('lpDebugTraceBodyBlobBytesWritten', bodyBlobBytesWritten)
  def preview = previewText(safeFull)
  return [
    contentType: contentType,
    text: preview,
    inlinePreview: preview,
    bodyStorage: 'sidecar',
    bodyTruncated: true,
    sizeBytes: safeBytes.length,
    sha256Prefix: sha256Prefix(safeBytes),
    downloadRelativePath: 'artifacts/debug-http-body-blobs/' + fileName
  ]
}
def bodyObj = { contentType, payload, seq, bodyKind ->
  byte[] originalBytes = bytesForPayload(payload)
  if (!shouldPreviewBody(contentType, payload)) {
    return droppedBody(contentType, originalBytes, 'binary_body')
  }
  def text = payload instanceof byte[] ? new String(payload, 'UTF-8') : String.valueOf(payload ?: '')
  if (originalBytes.length > bodyMaxBytes) {
    return sidecarBody(contentType, originalBytes, seq, bodyKind)
  }
  def raw = sanitizeBodyText(contentType, text)
  def bytes = raw.getBytes('UTF-8')
  def shown = previewText(raw)
  def storage = bytes.length > bodyMaxBytes ? 'truncated' : 'inline'
  return [
    contentType: contentType,
    text: shown,
    inlinePreview: shown,
    bodyStorage: storage,
    bodyTruncated: bytes.length > bodyMaxBytes,
    sizeBytes: originalBytes.length,
    sha256Prefix: sha256Prefix(originalBytes)
  ]
}
def markTraceTruncated = {
  if (vars.getObject('lpDebugTraceTruncated')) {
    return
  }
  def marker = JsonOutput.toJson([schemaVersion: 1, traceTruncated: true]) + System.lineSeparator()
  if (!out.exists() || out.length() + marker.getBytes('UTF-8').length <= artifactMaxBytes) {
    out << marker
  }
  vars.putObject('lpDebugTraceTruncated', true)
}
def markerBytes = (JsonOutput.toJson([schemaVersion: 1, traceTruncated: true]) + System.lineSeparator()).getBytes('UTF-8')
long reservedArtifactMaxBytes = Math.max(0L, artifactMaxBytes - markerBytes.length)
try {
def argsText = ''
try { argsText = sampler?.getArguments()?.toString() ?: '' } catch (Throwable ignored) { argsText = '' }
def nextSeq = (vars.getObject('lpDebugTraceSeq') ?: 0) + 1
if (nextSeq > maxRequests) {
  vars.putObject('lpDebugTraceSeq', nextSeq)
  markTraceTruncated()
  return
}
if (out.exists() && out.length() > reservedArtifactMaxBytes) {
  vars.putObject('lpDebugTraceSeq', nextSeq)
  markTraceTruncated()
  return
}
def requestHeaders = [:]
try {
	  sampler?.getHeaderManager()?.getHeaders()?.each { header ->
	    def key = String.valueOf(header.getName())
	    requestHeaders[key] = redactName(key) ? '[REDACTED]' : sanitizeFreeText(header.getValue())
	  }
} catch (Throwable ignored) { requestHeaders = [:] }
def requestContentType = requestHeaders.find { key, value -> String.valueOf(key).equalsIgnoreCase('content-type') }?.value
def requestBody = bodyObj(requestContentType, argsText, nextSeq, 'request')
def responseContentType = prev.getContentType()
def responsePayload = prev.getResponseData()
def responseBody = bodyObj(responseContentType, responsePayload, nextSeq, 'response')
def row = [
  schemaVersion: 1,
  sequence: nextSeq,
  label: sanitizeFreeText(prev.getSampleLabel()),
  url: sanitizeUrl(prev.getURL()),
  method: String.valueOf(sampler?.getMethod() ?: ''),
  requestHeaders: requestHeaders,
  requestBody: requestBody,
  responseStatus: (prev.getResponseCode()?.isInteger() ? prev.getResponseCode().toInteger() : null),
  responseHeaders: redactHeaders(prev.getResponseHeaders()),
  responseBody: responseBody,
  durationMs: prev.getTime(),
  error: prev.isSuccessful() ? null : sanitizeFreeText(prev.getResponseMessage()),
  bodyTruncated: requestBody.bodyTruncated || responseBody.bodyTruncated,
  traceTruncated: false
]
vars.putObject('lpDebugTraceSeq', row.sequence)
def encodedRow = JsonOutput.toJson(row) + System.lineSeparator()
if (encodedRow.getBytes('UTF-8').length > recordMaxBytes) {
  row.requestBody = droppedBody(requestContentType, bytesForPayload(argsText), 'record_too_large')
  row.responseBody = droppedBody(responseContentType, responsePayload, 'record_too_large')
  row.bodyTruncated = true
  encodedRow = JsonOutput.toJson(row) + System.lineSeparator()
}
if (encodedRow.getBytes('UTF-8').length > recordMaxBytes) {
  markTraceTruncated()
  return
}
if (out.exists() && out.length() + encodedRow.getBytes('UTF-8').length > reservedArtifactMaxBytes) {
  markTraceTruncated()
  return
}
if (!out.exists() && encodedRow.getBytes('UTF-8').length > reservedArtifactMaxBytes) {
  markTraceTruncated()
  return
}
out << encodedRow
} catch (Throwable traceError) {
  try { log.warn('Debug HTTP trace capture failed', traceError) } catch (Throwable ignored) {}
}
""".strip()


def debug_http_trace_jsr223_script(
    *,
    max_requests: int = 100,
    body_max_bytes: int = 65536,
    artifact_max_bytes: int = 10 * 1024 * 1024,
    record_max_bytes: int = 128 * 1024,
    body_blob_max_bytes: int = 5 * 1024 * 1024,
    body_blob_total_max_bytes: int = 20 * 1024 * 1024,
) -> str:
    return (
        DEBUG_HTTP_TRACE_JSR223_SCRIPT_TEMPLATE.replace(
            "__MAX_REQUESTS__", str(max(0, max_requests))
        )
        .replace("__BODY_MAX_BYTES__", str(max(0, body_max_bytes)))
        .replace("__RECORD_MAX_BYTES__", str(max(0, record_max_bytes)))
        .replace("__BODY_BLOB_MAX_BYTES__", str(max(0, body_blob_max_bytes)))
        .replace("__BODY_BLOB_TOTAL_MAX_BYTES__", str(max(0, body_blob_total_max_bytes)))
        .replace("__ARTIFACT_MAX_BYTES__", str(max(0, artifact_max_bytes)))
    )


def inject_debug_http_trace(
    document: dict[str, Any],
    *,
    max_requests: int = 100,
    body_max_bytes: int = 65536,
    artifact_max_bytes: int = 10 * 1024 * 1024,
    record_max_bytes: int = 128 * 1024,
    body_blob_max_bytes: int = 5 * 1024 * 1024,
    body_blob_total_max_bytes: int = 20 * 1024 * 1024,
) -> dict[str, Any]:
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, dict):
        return document
    script = debug_http_trace_jsr223_script(
        max_requests=max_requests,
        body_max_bytes=body_max_bytes,
        artifact_max_bytes=artifact_max_bytes,
        record_max_bytes=record_max_bytes,
        body_blob_max_bytes=body_blob_max_bytes,
        body_blob_total_max_bytes=body_blob_total_max_bytes,
    )
    for scenario in scenarios.values():
        if not isinstance(scenario, dict):
            continue
        requests = scenario.get("requests")
        if not isinstance(requests, list):
            continue
        for request in requests:
            if not isinstance(request, dict):
                continue
            existing = request.get("jsr223")
            trace_block = {
                "language": "groovy",
                "execute": "after",
                "script-text": script,
            }
            if existing is None:
                request["jsr223"] = trace_block
            elif isinstance(existing, list):
                request["jsr223"] = [*existing, trace_block]
            else:
                request["jsr223"] = [existing, trace_block]
    return document

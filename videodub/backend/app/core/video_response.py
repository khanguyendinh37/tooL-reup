"""Byte-range video delivery for the bundled Starlette version."""
import os
import re

from starlette.requests import Request
from starlette.responses import FileResponse, Response, StreamingResponse


def video_response(path: str, request: Request, filename: str | None = None):
    full = FileResponse(path, media_type="video/mp4", filename=filename,
                        stat_result=os.stat(path), headers={"Accept-Ranges": "bytes"})
    value = request.headers.get("range")
    if not value or request.headers.get("if-range") not in (
        None, full.headers.get("etag"), full.headers.get("last-modified")
    ):
        return full
    # Multiple ranges and unknown units may be ignored with a full response.
    if ',' in value or not value.startswith('bytes='):
        return full
    size = os.path.getsize(path)
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
    try:
        if not match or not any(match.groups()):
            raise ValueError
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        else:
            start, end = max(0, size - int(last)), size - 1
        if start > end or start >= size:
            raise ValueError
    except ValueError:
        return Response(status_code=416, headers={
            "Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes",
        })

    def chunks():
        with open(path, 'rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = dict(full.headers)
    headers['content-range'] = f'bytes {start}-{end}/{size}'
    headers['content-length'] = str(end - start + 1)
    return StreamingResponse(chunks(), status_code=206, headers=headers,
                             media_type='video/mp4')

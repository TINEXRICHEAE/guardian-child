"""Validate uploaded screenshots and re-encode them (drops EXIF, caps size) before any model sees them."""
import io

from PIL import Image, UnidentifiedImageError


class ImageRejected(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _sniff(data: bytes) -> str | None:
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def prepare_image(data: bytes, *, max_bytes: int, max_side: int) -> tuple[bytes, str]:
    """Return (clean_bytes, mime). Raises ImageRejected with an HTTP status code."""
    if not data:
        raise ImageRejected(400, 'Empty file.')
    if len(data) > max_bytes:
        raise ImageRejected(413, f'Image is larger than {max_bytes // (1024 * 1024)} MB.')
    mime = _sniff(data)
    if mime is None:
        raise ImageRejected(415, 'Only PNG, JPEG or WebP screenshots are accepted.')
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImageRejected(415, f'The image could not be read: {type(e).__name__}.') from e

    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    if mime == 'image/jpeg':
        img.convert('RGB').save(out, format='JPEG', quality=90)
    else:
        if img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
            img = img.convert('RGBA')
        img.save(out, format='PNG')
        mime = 'image/png'
    return out.getvalue(), mime

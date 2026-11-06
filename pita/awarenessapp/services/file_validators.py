import os

ALLOWED_EXTENSIONS = {'.pdf', '.txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_PDF_MAGIC = b'%PDF'


def validate_document_upload(uploaded_file):
    """
    Validate an uploaded document file.

    Returns (True, None) on success or (False, error_message) on failure.
    Checks: extension whitelist, file size, and magic bytes for PDFs.
    """
    name = getattr(uploaded_file, 'name', '')
    ext = os.path.splitext(name)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f"Invalid file type '{ext}'. Only PDF (.pdf) and plain-text (.txt) files are accepted."
        )

    size = getattr(uploaded_file, 'size', None)
    if size is None:
        size = uploaded_file.seek(0, 2)  # seek to end
        uploaded_file.seek(0)
    if size > MAX_FILE_SIZE:
        mb = size // (1024 * 1024)
        return False, f"File is too large ({mb} MB). Maximum allowed size is 10 MB."

    if ext == '.pdf':
        header = uploaded_file.read(4)
        uploaded_file.seek(0)
        if header != _PDF_MAGIC:
            return False, "The uploaded file does not appear to be a valid PDF."

    if ext == '.txt':
        chunk = uploaded_file.read(512)
        uploaded_file.seek(0)
        try:
            chunk.decode('utf-8')
        except UnicodeDecodeError:
            try:
                chunk.decode('latin-1')
            except Exception:
                return False, "The TXT file contains unreadable characters and cannot be processed."

    return True, None

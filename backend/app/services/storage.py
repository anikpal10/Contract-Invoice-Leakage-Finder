import os
import hashlib
import shutil
from typing import Tuple
from fastapi import UploadFile, HTTPException
from backend.app.core.config import settings

class StorageService:
    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.local_dir = os.path.abspath(settings.LOCAL_STORAGE_DIR)
        self.export_dir = os.path.abspath(settings.LOCAL_EXPORT_DIR)
        os.makedirs(self.local_dir, exist_ok=True)
        os.makedirs(self.export_dir, exist_ok=True)

    def save_upload(self, case_id: str, file: UploadFile) -> Tuple[str, str, int, str]:
        """
        Saves uploaded file to local filesystem or GCS.
        Returns: (saved_filename, relative_storage_path, file_size, sha256_hash)
        """
        extension = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if extension not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type .{extension}. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        case_folder = os.path.join(self.local_dir, case_id)
        os.makedirs(case_folder, exist_ok=True)

        # Compute SHA256 while writing file
        hasher = hashlib.sha256()
        file_size = 0
        
        # Unique safe temp filename using a random token to prevent collision
        import uuid
        temp_name = f"tmp_{uuid.uuid4().hex[:10]}_{file.filename}"
        dest_path = os.path.join(case_folder, temp_name)

        try:
            with open(dest_path, "wb") as buffer:
                while chunk := file.file.read(1024 * 64):
                    hasher.update(chunk)
                    buffer.write(chunk)
                    file_size += len(chunk)
                    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB"
                        )
        except Exception as e:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise e

        sha256_hash = hasher.hexdigest()
        # Rename to include actual SHA256 prefix safely on Windows (handles existing destination)
        final_filename = f"{sha256_hash[:12]}_{file.filename}"
        final_path = os.path.join(case_folder, final_filename)
        if os.path.exists(final_path):
            if os.path.exists(dest_path):
                os.remove(dest_path)
        else:
            os.replace(dest_path, final_path)

        return final_filename, final_path, file_size, sha256_hash

    def register_file_by_path(self, file_path: str) -> Tuple[str, str, int, str]:
        """
        Directly accesses an existing file on disk by its path without copying
        or holding the file in memory. Streams directly from disk for hashing.
        """
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail=f"File not found on disk at: {abs_path}")

        filename = os.path.basename(abs_path)
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file extension .{ext}. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # Compute SHA-256 by streaming directly from disk (zero-memory buffer)
        hasher = hashlib.sha256()
        file_size = 0
        with open(abs_path, "rb") as f:
            while chunk := f.read(1024 * 64):
                hasher.update(chunk)
                file_size += len(chunk)

        sha256_hash = hasher.hexdigest()
        return filename, abs_path, file_size, sha256_hash

    def get_file_content(self, storage_path: str) -> bytes:
        if not os.path.exists(storage_path):
            raise FileNotFoundError(f"File not found at {storage_path}")
        with open(storage_path, "rb") as f:
            return f.read()

storage_service = StorageService()


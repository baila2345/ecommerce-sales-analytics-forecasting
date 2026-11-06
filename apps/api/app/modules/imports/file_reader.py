import hashlib
from pathlib import Path

from fastapi import UploadFile, status

from app.core.errors import AppError
from app.modules.imports.domain import UploadedCsv


class CsvUploadReader:
    def __init__(self, max_file_size_bytes: int) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    async def read(self, upload: UploadFile) -> UploadedCsv:
        filename = Path(upload.filename or "").name
        if not filename or Path(filename).suffix.lower() != ".csv":
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="CSV_FILE_REQUIRED",
                message="Please select a CSV file",
            )

        content = await upload.read(self.max_file_size_bytes + 1)
        await upload.close()
        if len(content) > self.max_file_size_bytes:
            max_size_mb = self.max_file_size_bytes // (1024 * 1024)
            raise AppError(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                code="CSV_FILE_TOO_LARGE",
                message=f"The CSV file must not exceed {max_size_mb} MB",
            )
        if not content:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="CSV_FILE_EMPTY",
                message="The CSV file is empty",
            )

        return UploadedCsv(
            filename=filename,
            content=content,
            checksum_sha256=hashlib.sha256(content).hexdigest(),
        )

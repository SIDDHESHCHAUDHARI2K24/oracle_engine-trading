"""CSV import endpoint for bulk membership addition."""

import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service
from app.features.universes.schemas import AddResult

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 50_000


class ImportResult(AddResult):
    parse_errors: list[str] = []


import_membership_router = APIRouter(tags=["membership-import"])


@import_membership_router.post(
    "/{universe_id}/membership/import",
    response_model=ImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_csv(
    universe_id: uuid.UUID,
    file: UploadFile = File(...),
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> ImportResult:
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error_code": "FILE_TOO_LARGE",
                "message": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit",
            },
        )

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error_code": "FILE_TOO_LARGE",
                "message": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit",
            },
        )

    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    symbols: list[str] = []
    parse_errors: list[str] = []
    row_count = 0

    for idx, row in enumerate(reader):
        if not row:
            continue
        cell = row[0].strip()
        if not cell:
            continue
        # Skip header row if it looks like one
        if idx == 0 and cell.lower() in ("symbol", "ticker", "code"):
            continue

        row_count += 1
        if row_count > MAX_ROWS:
            parse_errors.append(f"Row {idx + 1}: exceeded max row limit of {MAX_ROWS}")
            continue

        symbols.append(cell)

    if not symbols and not parse_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "EMPTY_FILE",
                "message": "No valid symbols found in uploaded file",
            },
        )

    try:
        result = await universes_service.add_members(db, universe_id, symbols)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "UNIVERSE_NOT_FOUND",
                "message": str(exc),
            },
        )

    await db.commit()
    return ImportResult(
        added=result.added,
        already_present=result.already_present,
        invalid=result.invalid,
        parse_errors=parse_errors,
    )

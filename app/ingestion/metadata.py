from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.db.models import Document
from app.ingestion.loaders import LoadedBlock


# ============================================================
# CHUNK METADATA
# ============================================================


@dataclass(slots=True)
class ChunkMetadata:
    """
    Metadata attached to every chunk.

    This structure is designed for both:

        1. Vector DB metadata
        2. Citation generation

    SQL remains the source of truth for authorization.
    The access fields here are metadata copied from the
    authoritative Document record.
    """

    # --------------------------------------------------------
    # Document identity
    # --------------------------------------------------------

    document_id: int

    document_key: str

    title: str

    filename: str

    relative_path: str

    source_type: str

    version: int

    checksum: str

    # --------------------------------------------------------
    # Security metadata
    # --------------------------------------------------------

    classification: str

    access_scope: str

    owner_department_id: int

    owner_department_code: str

    # --------------------------------------------------------
    # Source location
    # --------------------------------------------------------

    page_number: int | None = None

    section: str | None = None

    sheet_name: str | None = None

    row_start: int | None = None

    row_end: int | None = None

    line_start: int | None = None

    line_end: int | None = None

    # --------------------------------------------------------
    # Chunk identity
    # --------------------------------------------------------

    chunk_index: int = 0

    # --------------------------------------------------------
    # Citation-friendly display string
    # --------------------------------------------------------

    citation: str = ""

    # ========================================================
    # SERIALIZATION
    # ========================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert metadata into a dictionary suitable for
        Chroma metadata.

        None values are removed because vector databases
        generally prefer scalar metadata values.
        """

        data = asdict(self)

        return {
            key: value
            for key, value in data.items()
            if value is not None
        }


# ============================================================
# CITATION LOCATION
# ============================================================


def build_citation_location(
    block: LoadedBlock,
) -> str:
    """
    Build the location portion of a citation.
    """

    parts: list[str] = []

    if block.page_number is not None:
        parts.append(
            f"page {block.page_number}"
        )

    if block.section:
        parts.append(
            f"section: {block.section}"
        )

    if block.sheet_name:
        parts.append(
            f"sheet: {block.sheet_name}"
        )

    if (
        block.row_start is not None
        and block.row_end is not None
    ):
        parts.append(
            f"rows {block.row_start}-{block.row_end}"
        )

    if (
        block.line_start is not None
        and block.line_end is not None
    ):
        parts.append(
            f"lines {block.line_start}-{block.line_end}"
        )

    if not parts:
        return "document"

    return " · ".join(parts)


# ============================================================
# FULL CITATION
# ============================================================


def build_citation(
    document: Document,
    block: LoadedBlock,
) -> str:
    """
    Build a human-readable citation.

    Examples:

        Q2 Financial Review — page 3

        Engineering Architecture — section:
        Data Flow

        Campaign Performance — sheet:
        Campaigns · rows 1-6
    """

    location = build_citation_location(
        block
    )

    return (
        f"{document.title} — "
        f"{location}"
    )


# ============================================================
# METADATA BUILDER
# ============================================================


def build_chunk_metadata(
    document: Document,
    block: LoadedBlock,
    chunk_index: int,
) -> ChunkMetadata:
    """
    Combine database document metadata with
    source-specific location metadata.
    """

    citation = build_citation(
        document,
        block,
    )

    return ChunkMetadata(
        document_id=document.id,
        document_key=document.document_key,
        title=document.title,
        filename=document.filename,
        relative_path=document.relative_path,
        source_type=document.source_type,
        version=document.version,
        checksum=document.checksum,

        classification=document.classification,
        access_scope=document.access_scope,

        owner_department_id=(
            document.owner_department_id
        ),

        owner_department_code=(
            document.owner_department.code
        ),

        page_number=block.page_number,
        section=block.section,
        sheet_name=block.sheet_name,
        row_start=block.row_start,
        row_end=block.row_end,
        line_start=block.line_start,
        line_end=block.line_end,

        chunk_index=chunk_index,

        citation=citation,
    )
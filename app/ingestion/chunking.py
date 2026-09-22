from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.db.models import Document
from app.ingestion.loaders import LoadedBlock
from app.ingestion.metadata import (
    ChunkMetadata,
    build_chunk_metadata,
)


# ============================================================
# CHUNK
# ============================================================


@dataclass(slots=True)
class Chunk:
    """
    Final retrieval-ready chunk.

    Each chunk contains:
        - deterministic chunk ID
        - text used for embedding
        - rich source/security metadata
    """

    chunk_id: str
    text: str
    metadata: ChunkMetadata

    @property
    def chroma_metadata(self) -> dict:
        """
        Metadata ready to be stored in Chroma.
        """

        return self.metadata.to_dict()


# ============================================================
# TEXT NORMALIZATION
# ============================================================


def normalize_chunk_text(text: str) -> str:
    """
    Normalize extracted text before chunking/embedding.

    Keeps paragraph boundaries while removing:
        - null characters
        - excessive spaces
        - excessive blank lines
    """

    text = text.replace("\x00", "")

    # Normalize line endings.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Collapse spaces/tabs but preserve newlines.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Avoid excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# TEXT SPLITTER
# ============================================================


def split_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[str]:
    """
    Split text into approximately `chunk_size` character chunks
    while preserving word boundaries.

    `overlap` specifies an approximate number of characters
    repeated between neighbouring chunks.

    Example:

        chunk_size = 1200
        overlap    = 150

    gives approximately:

        Chunk 1: characters 0-1200
        Chunk 2: ~1050-2250
        Chunk 3: ~2100-3300

    This is a character-based splitter, not a token-based
    splitter. That is intentional for the current prototype.

    Later, this can be replaced by a token-aware splitter
    without changing the rest of the ingestion architecture.
    """

    # --------------------------------------------------------
    # Validate configuration
    # --------------------------------------------------------

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    # --------------------------------------------------------
    # Normalize input
    # --------------------------------------------------------

    text = normalize_chunk_text(text)

    if not text:
        return []

    # Small enough to remain a single chunk.
    if len(text) <= chunk_size:
        return [text]

    words = text.split()

    chunks: list[str] = []

    start = 0

    # --------------------------------------------------------
    # Sliding window over words
    # --------------------------------------------------------

    while start < len(words):

        current_words: list[str] = []
        current_length = 0

        end = start

        # ----------------------------------------------------
        # Fill current chunk
        # ----------------------------------------------------

        while end < len(words):

            word = words[end]

            addition = (
                len(word)
                if not current_words
                else len(word) + 1
            )

            # Don't exceed chunk_size.
            if (
                current_words
                and current_length + addition
                > chunk_size
            ):
                break

            current_words.append(word)

            current_length += addition

            end += 1

        # ----------------------------------------------------
        # Extremely long individual word/token
        # ----------------------------------------------------

        if not current_words:

            current_words = [
                words[end]
            ]

            end += 1

        chunk = " ".join(
            current_words
        ).strip()

        if chunk:
            chunks.append(chunk)

        # ----------------------------------------------------
        # Finished
        # ----------------------------------------------------

        if end >= len(words):
            break

        # ----------------------------------------------------
        # Calculate overlap
        #
        # Walk backwards from the end of the current chunk
        # until approximately `overlap` characters are covered.
        # ----------------------------------------------------

        overlap_length = 0

        overlap_start = end

        for index in range(
            len(current_words) - 1,
            -1,
            -1,
        ):

            word = current_words[index]

            additional = len(word)

            if overlap_length > 0:
                additional += 1

            if (
                overlap_length + additional
                > overlap
            ):
                break

            overlap_length += additional

            overlap_start = (
                start + index
            )

        # ----------------------------------------------------
        # Make absolutely sure the next iteration progresses.
        # ----------------------------------------------------

        if overlap_start <= start:
            start = end
        else:
            start = overlap_start

    return chunks


# ============================================================
# DETERMINISTIC CHUNK ID
# ============================================================


def build_chunk_id(
    document: Document,
    chunk_index: int,
    text: str,
) -> str:
    """
    Generate a deterministic chunk ID.

    The ID depends on:

        document key
        document version
        chunk index
        chunk text

    Therefore, if a document changes and its version changes,
    its chunk IDs also change.
    """

    raw = (
        f"{document.document_key}:"
        f"{document.version}:"
        f"{chunk_index}:"
        f"{text}"
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

    return f"CHUNK-{digest[:24]}"


# ============================================================
# DOCUMENT CHUNKING
# ============================================================


def chunk_document(
    document: Document,
    blocks: list[LoadedBlock],
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[Chunk]:
    """
    Convert loaded source blocks into retrieval-ready chunks.

    Important design rule:

        Source blocks are NEVER mixed together.

    Examples:

        PDF page 3
            -> chunks belonging to page 3

        XLSX / Campaigns sheet rows 1-25
            -> chunks belonging to that sheet/range

        Markdown section
            -> chunks retaining that section

    This makes downstream citations substantially more reliable.
    """

    chunks: list[Chunk] = []

    global_chunk_index = 0

    for block in blocks:

        block_chunks = split_text(
            block.text,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for text in block_chunks:

            text = normalize_chunk_text(text)

            if not text:
                continue

            metadata = build_chunk_metadata(
                document=document,
                block=block,
                chunk_index=global_chunk_index,
            )

            chunk_id = build_chunk_id(
                document=document,
                chunk_index=global_chunk_index,
                text=text,
            )

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=text,
                    metadata=metadata,
                )
            )

            global_chunk_index += 1

    return chunks
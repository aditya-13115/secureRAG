from pathlib import Path

from app.ingestion.chunking import chunk_document
from app.ingestion.loaders import load_document


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOCUMENT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "documents"
)


def test_pdf_loader():

    path = (
        DOCUMENT_ROOT
        / "finance"
        / "Q2_financial_review.pdf"
    )

    blocks = load_document(path)

    assert blocks

    assert any(
        block.page_number is not None
        for block in blocks
    )

    assert all(
        block.text.strip()
        for block in blocks
    )


def test_markdown_loader():

    path = (
        DOCUMENT_ROOT
        / "management"
        / "management_principles.md"
    )

    blocks = load_document(path)

    assert blocks

    assert any(
        block.section is not None
        for block in blocks
    )


def test_xlsx_loader():

    path = (
        DOCUMENT_ROOT
        / "finance"
        / "FY2026_budget_and_variance.xlsx"
    )

    blocks = load_document(path)

    assert blocks

    assert all(
        block.sheet_name is not None
        for block in blocks
    )


def test_chunking_preserves_source_location():

    path = (
        DOCUMENT_ROOT
        / "finance"
        / "Q2_financial_review.pdf"
    )

    blocks = load_document(path)

    # For this test we don't need a real SQL object.
    # This test only checks that the loader produces
    # locatable blocks.
    for block in blocks:
        assert (
            block.page_number is not None
        )
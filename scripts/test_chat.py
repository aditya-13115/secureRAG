from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import User
from app.llm.service import SecureRAGService


async def main() -> None:
    db = SessionLocal()

    try:
        user = db.execute(
            select(User).where(
                User.email
                == "engineer@monke.ai"
            )
        ).scalar_one()

        service = SecureRAGService()

        query = (
            "What is the current status of "
            "the SecureRAG prototype?"
        )

        print()
        print("=" * 80)
        print("SECURERAG CHAT TEST")
        print("=" * 80)
        print(
            f"User  : {user.email}"
        )
        print(
            f"Query : {query}"
        )
        print("=" * 80)

        result = await service.answer(
            db=db,
            user=user,
            query=query,
            top_k=8,
        )

        print()
        print("ANSWER")
        print("-" * 80)
        print(result.answer)

        print()
        print("SOURCES")
        print("-" * 80)

        for citation in result.citations:
            print(
                f"[{citation.source_id}] "
                f"{citation.citation}"
            )

        print()
        print("METADATA")
        print("-" * 80)
        print(
            f"Model          : {result.model}"
        )
        print(
            f"Retrieved      : "
            f"{len(result.retrieved_results)}"
        )
        print(
            f"Prompt tokens  : "
            f"{result.usage_prompt_tokens}"
        )
        print(
            f"Completion     : "
            f"{result.usage_completion_tokens}"
        )
        print(
            f"Total tokens   : "
            f"{result.usage_total_tokens}"
        )

        # Key slot is intentionally not printed here.
        # The client logs it internally without exposing the key.

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(
        main()
    )
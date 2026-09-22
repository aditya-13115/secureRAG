from __future__ import annotations

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import User
from app.retrieval.retriever import SecureRetriever


def print_result(
    index: int,
    result,
) -> None:
    print()
    print("-" * 80)
    print(
        f"#{index} | "
        f"Hybrid Score: {result.score:.6f}"
    )
    print(
        f"Document ID : {result.document_id}"
    )
    print(
        f"Sources     : "
        f"{', '.join(result.sources) or 'unknown'}"
    )
    print(
        f"Citation    : {result.citation}"
    )
    print()
    print(
        result.text[:700]
    )


def main() -> None:
    db = SessionLocal()

    try:
        # ---------------------------------------------------------
        # User
        # ---------------------------------------------------------
        user = db.execute(
            select(User).where(
                User.email == "engineer@monke.ai"
            )
        ).scalar_one()

        # ---------------------------------------------------------
        # SecureRetriever
        #
        # Internally:
        #   SQL ACL
        #      ↓
        #   Semantic 65%
        #      +
        #   BM25 35%
        #      ↓
        #   Weighted RRF
        # ---------------------------------------------------------
        retriever = SecureRetriever()

        allowed_document_ids = (
            retriever.get_allowed_document_ids(
                db=db,
                user=user,
            )
        )

        query = (
            "What were the Q3 revenue drivers?"
        )

        print()
        print("=" * 80)
        print("SECURERAG HYBRID RETRIEVAL")
        print("=" * 80)
        print(
            f"User                : {user.email}"
        )
        print(
            f"Allowed documents   : "
            f"{len(allowed_document_ids)}"
        )
        print(
            f"Semantic weight     : 65%"
        )
        print(
            f"BM25 weight         : 35%"
        )
        print(
            f"Query               : {query}"
        )
        print("=" * 80)

        # ---------------------------------------------------------
        # Retrieval
        # ---------------------------------------------------------
        results = retriever.search(
            db=db,
            user=user,
            query=query,
            top_k=10,
            candidate_k=30,
            rrf_k=60,
        )

        if not results:
            print("\nNo results found.")
            return

        print(
            f"\nReturned results: "
            f"{len(results)}"
        )

        # ---------------------------------------------------------
        # Results
        # ---------------------------------------------------------
        for index, result in enumerate(
            results,
            start=1,
        ):
            print_result(
                index,
                result,
            )

        # ---------------------------------------------------------
        # Security verification
        # ---------------------------------------------------------
        allowed_set = set(
            allowed_document_ids
        )

        unauthorized = [
            result
            for result in results
            if result.document_id
            not in allowed_set
        ]

        print()
        print("=" * 80)
        print("SECURITY CHECK")
        print("=" * 80)

        if unauthorized:
            print(
                "❌ SECURITY FAILURE"
            )

            for result in unauthorized:
                print(
                    f"Unauthorized document: "
                    f"{result.document_id}"
                )
        else:
            print(
                "✅ All returned chunks belong "
                "to documents the user is authorized to access."
            )

        # ---------------------------------------------------------
        # Ranking check
        # ---------------------------------------------------------
        scores = [
            result.score
            for result in results
        ]

        if scores == sorted(
            scores,
            reverse=True,
        ):
            print(
                "✅ Results are ordered by "
                "descending hybrid RRF score."
            )
        else:
            print(
                "❌ Result ordering is invalid."
            )

        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()
from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.llm.client import (
    GroqRequestError,
    GroqUnavailableError,
)
from app.llm.service import (
    SecureRAGService,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationResponse,
)


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


def get_current_user(
    x_user_email: str | None,
    db: Session,
) -> User:
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "X-User-Email header is required."
            ),
        )

    email = x_user_email.strip()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User email cannot be empty.",
        )

    user = db.execute(
        select(User).where(
            User.email == email
        )
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    x_user_email: str | None = Header(
        default=None
    ),
    db: Session = Depends(get_db),
) -> ChatResponse:

    user = get_current_user(
        x_user_email=x_user_email,
        db=db,
    )

    service = SecureRAGService()

    try:
        result = await service.answer(
            db=db,
            user=user,
            query=request.query,
            top_k=request.top_k,
        )

    except GroqUnavailableError as exc:
        headers = {}

        if exc.retry_after is not None:
            headers["Retry-After"] = str(
                int(
                    max(
                        exc.retry_after,
                        1,
                    )
                )
            )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers=headers,
        ) from exc

    except GroqRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return ChatResponse(
        answer=result.answer,
        citations=[
            CitationResponse(
                source_id=citation.source_id,
                citation=citation.citation,
                document_id=citation.document_id,
            )
            for citation in result.citations
        ],
        retrieval_count=len(
            result.retrieved_results
        ),
        model=result.model,
        prompt_tokens=(
            result.usage_prompt_tokens
        ),
        completion_tokens=(
            result.usage_completion_tokens
        ),
        total_tokens=(
            result.usage_total_tokens
        ),
    )
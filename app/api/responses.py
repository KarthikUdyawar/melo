from typing import Any

from fastapi.responses import JSONResponse

from app.schemas.envelope import Envelope


def envelope_response(
    data: Any,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    envelope = Envelope(status_code=status_code, message=message, body=data)
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )


def paginated_response(
    records: list[Any],
    count: int,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    body = {"records": records, "count": count}
    envelope = Envelope(status_code=status_code, message=message, body=body)
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )

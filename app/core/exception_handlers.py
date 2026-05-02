from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.envelope import Envelope


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    envelope: Envelope[None] = Envelope(
        status_code=exc.status_code,
        message=str(exc.detail),
        body=None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope.model_dump(mode="json"),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    message = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors
    )
    envelope: Envelope[None] = Envelope(status_code=422, message=message, body=None)
    return JSONResponse(
        status_code=422,
        content=envelope.model_dump(mode="json"),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    envelope: Envelope[None] = Envelope(
        status_code=500,
        message="Internal server error.",
        body=None,
    )
    return JSONResponse(
        status_code=500,
        content=envelope.model_dump(mode="json"),
    )

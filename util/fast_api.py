from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from starlette.requests import Request
from starlette.status import (
    HTTP_422_UNPROCESSABLE_ENTITY as _422
)

def to_fast_api(lifespan):

    fast_api = FastAPI(lifespan=lifespan)

    fast_api.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # Handle common FastAPI exceptions
    @fast_api.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        content = {'status_code': 10422, 'data': None}
        print(f'{exc}'.replace('\n', ' ').replace('   ', ' '))
        return JSONResponse(content=content, status_code=_422)

    return fast_api

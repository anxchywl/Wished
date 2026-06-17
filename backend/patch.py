import sys

content = open('app/main.py').read()
replacement = """
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation Error: {exc.errors()}", flush=True)
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

"""
if "RequestValidationError" not in content:
    content = content.replace('app = FastAPI(', 'app = FastAPI(\n\n' + replacement + '\n\n')
    open('app/main.py', 'w').read() # oops wait...

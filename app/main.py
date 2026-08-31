from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.products import router as product_router
from app.core.exceptions import ProductNotFoundException


app = FastAPI()


@app.exception_handler(ProductNotFoundException)
async def product_not_found_handler(
    request: Request,
    exc: ProductNotFoundException
):
    return JSONResponse(
        status_code=404,
        content={
            "detail": str(exc)
        }
    )

app.include_router(product_router)


@app.get("/")
async def root():
    return {"message": "API is running"}

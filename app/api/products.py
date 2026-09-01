from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy import select

from app.database.connection import AsyncSessionLocal
from app.models.product import Product
from app.database.connection import get_db
from sqlalchemy.ext.asyncio import AsyncSession


from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse
)
from app.services import chat_service, product_service

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.post("/", response_model=ProductResponse)
async def create_product(product: ProductCreate,
                         session: AsyncSession = Depends(get_db)
                         ):

    return await product_service.create_product(
        session,
        product
    )


@router.get("/", response_model=list[ProductResponse])
async def get_products(
    session: AsyncSession = Depends(get_db)
):

    return await product_service.get_products(session)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int,
                      session: AsyncSession = Depends(get_db)
                      ):

    return await product_service.get_product(
        session,
        product_id
    )


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    session: AsyncSession = Depends(get_db)
):

    return await product_service.update_product(
        session,
        product_id,
        product_data
    )


@router.delete("/{product_id}")
async def delete_product(product_id: int,
                         session: AsyncSession = Depends(get_db)
                         ):

    await product_service.delete_product(
        session, product_id)


# ---------------------------------------------------------------------------
# Single public endpoint
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await chat_service.chat(request)

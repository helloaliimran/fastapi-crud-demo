from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ProductNotFoundException
from app.models.product import Product
from app.schemas.product import ProductCreate
from app.repositories import product_repository


async def get_products(
    session: AsyncSession
):

    return await product_repository.get_all(session)


async def get_product(
    session: AsyncSession,
    product_id: int
):
    db_product = await product_repository.get_by_id(session, product_id)
    if db_product is None:
        raise ProductNotFoundException(product_id)

    return db_product


async def create_product(
    session: AsyncSession,
    product: ProductCreate
):
    new_product = Product(
        name=product.name,
        price=product.price
    )

    return await product_repository.create(session, new_product)


async def update_product(
    session: AsyncSession,
    product_id: int,
    product: ProductCreate
):
    db_product = await product_repository.get_by_id(
        session,
        product_id
    )

    if db_product is None:
        raise ProductNotFoundException(product_id)

    db_product.name = product.name
    db_product.price = product.price

    return await product_repository.update(
        session,
        db_product
    )


async def delete_product(
    session: AsyncSession,
    product_id: int
):
    db_product = await product_repository.get_by_id(
        session,
        product_id
    )

    if db_product is None:
        raise ProductNotFoundException(product_id)

    await product_repository.delete(
        session,
        db_product
    )

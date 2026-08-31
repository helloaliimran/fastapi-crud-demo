from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


async def get_all(
    session: AsyncSession
):
    result = await session.execute(
        select(Product)
    )

    return result.scalars().all()


async def get_by_id(
    session: AsyncSession,
    product_id: int
):
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )

    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    product: Product
):
    session.add(product)

    await session.commit()
    await session.refresh(product)

    return product


async def delete(
    session: AsyncSession,
    product: Product
):
    await session.delete(product)
    await session.commit()


async def update(
    session: AsyncSession,
    product: Product
):
    await session.commit()
    await session.refresh(product)

    return product

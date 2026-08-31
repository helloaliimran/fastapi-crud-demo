from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    price: float


class ProductUpdate(BaseModel):
    name: str
    price: float


class ProductResponse(BaseModel):
    id: int
    name: str
    price: float

    model_config = {
        "from_attributes": True
    }

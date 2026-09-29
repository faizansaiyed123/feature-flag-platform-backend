from uuid import UUID

from pydantic import BaseModel, ConfigDict

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class IDResponse(ORMModel):
    id: UUID

class MessageResponse(BaseModel):
    message: str

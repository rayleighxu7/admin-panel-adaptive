from pydantic import BaseModel, Field


class PerOrderConfig(BaseModel):
    fee_cents: int = 0
    quantity_threshold: int = 0


class ConfigSchema(BaseModel):
    commission_percentage: float = Field(0, ge=0, le=1)
    affiliate_percentage: float = Field(0, ge=0, le=1)
    gmv_percentage: float = Field(0, ge=0, le=1)
    per_order: PerOrderConfig = PerOrderConfig()
    flat_fee_cents: int = Field(0, ge=0)

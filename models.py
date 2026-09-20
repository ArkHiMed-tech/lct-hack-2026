from pydantic import BaseModel
from pydantic.fields import Field

class User(BaseModel):
    login: str
    password: str
    email: str
    name: str | None = None
    last_name: str | None = None
    role: str | None = None
    group_name: str | None = None
    active: bool = True


class IncidentReport(BaseModel):
    user_id: str | None = None
    scenario_id: str | None = None
    what: str = Field(default="")
    incident_category: str = Field(default="")
    address: str = Field(default="")
    time: str = Field(default="")
    caller_name: str = Field(default="")
    victims: str = Field(default="")
    conditions: str = Field(default="")
    threat: str = Field(default="")
    factors: list[str] = Field(default_factory=list)
    actions: str = Field(default="")
    landmarks: str | None = None
    services: list[str] = Field(default_factory=list)
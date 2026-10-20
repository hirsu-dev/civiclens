from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

DecisionStatus = Literal["proposed", "approved", "denied", "tabled"]
Identifier = str


class Meeting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[\w.-]{1,100}$")
    date: date
    body: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    jurisdiction: str = Field(min_length=1, max_length=200)
    source_url: HttpUrl
    is_demo: bool = False


class AgendaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[\w.-]{1,100}$")
    meeting_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=5000)
    source_excerpt: str = Field(min_length=1, max_length=10000)
    topic: str = Field(min_length=1, max_length=80)
    status: DecisionStatus
    source_url: HttpUrl
    district: str = Field(default="Citywide", max_length=100)
    reference: str | None = Field(default=None, min_length=1, max_length=100)
    summary_method: Literal["human", "extractive", "demo"] = "human"


class ImportBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meetings: list[Meeting] = Field(min_length=1, max_length=500)
    items: list[AgendaItem] = Field(max_length=2000)

    @model_validator(mode="after")
    def unique_ids(self):
        for values in (self.meetings, self.items):
            ids = [v.id for v in values]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate IDs in import bundle")
        return self


class SavedSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    q: str = Field(default="", max_length=200)
    topic: str = Field(default="", max_length=80)
    status: DecisionStatus | None = None
    district: str = Field(default="", max_length=100)
    jurisdiction: str = Field(default="", max_length=200)

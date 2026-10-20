from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class Meeting(BaseModel):
    id: str
    date: date
    body: str
    title: str
    source_url: HttpUrl


class AgendaItem(BaseModel):
    id: str
    meeting_id: str
    title: str
    summary: str
    topic: str
    status: Literal["proposed", "approved", "denied", "tabled"]
    source_url: HttpUrl
    district: str | None = None


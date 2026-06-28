from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CIE10(Base):
    __tablename__ = "cie10"

    # Not using UUID, PK is the standard code (e.g. J06.9)
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)

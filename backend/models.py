from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass 

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key = True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] =  mapped_column(String(1000))

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key = True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete = "CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
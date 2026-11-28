from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("total_copies >= 0", name="ck_books_total_nonnegative"),
        CheckConstraint("available_copies >= 0", name="ck_books_available_nonnegative"),
        CheckConstraint("available_copies <= total_copies", name="ck_books_available_lte_total"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str] = mapped_column(String(160), index=True)
    isbn: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    total_copies: Mapped[int] = mapped_column(Integer, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, default=1)
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="book")


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Pending', 'Reserved', 'Rejected', 'Borrowed', 'Returned')",
            name="ck_reservations_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="Pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship(back_populates="reservations")
    book: Mapped[Book] = relationship(back_populates="reservations")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"), unique=True)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
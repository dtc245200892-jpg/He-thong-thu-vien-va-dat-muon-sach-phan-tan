from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Book, Reservation


class ReservationNotFound(Exception):
    pass


class InvalidReservationTransition(Exception):
    pass


def process_reservation(session: Session, reservation_id: int) -> str:
    with session.begin():
        reservation = session.scalar(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        )
        if reservation is None:
            raise ReservationNotFound
        if reservation.status != "Pending":
            return reservation.status

        book = session.scalar(select(Book).where(Book.id == reservation.book_id).with_for_update())
        if book is None:
            reservation.status = "Rejected"
        elif book.available_copies > 0:
            book.available_copies -= 1
            reservation.status = "Reserved"
        else:
            reservation.status = "Rejected"
        return reservation.status


def borrow_reservation(session: Session, reservation_id: int) -> Reservation:
    with session.begin():
        reservation = session.scalar(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        )
        if reservation is None:
            raise ReservationNotFound
        if reservation.status != "Reserved":
            raise InvalidReservationTransition
        reservation.status = "Borrowed"
    return reservation


def return_reservation(session: Session, reservation_id: int) -> Reservation:
    with session.begin():
        reservation = session.scalar(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        )
        if reservation is None:
            raise ReservationNotFound
        if reservation.status != "Borrowed":
            raise InvalidReservationTransition
        book = session.scalar(select(Book).where(Book.id == reservation.book_id).with_for_update())
        if book is None:
            raise ReservationNotFound
        book.available_copies += 1
        reservation.status = "Returned"
    return reservation
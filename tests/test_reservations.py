import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.db import Base
from app.models import Book, Reservation, User
from app.services import borrow_reservation, process_reservation, return_reservation


def make_session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def seed_reservation(session_factory, copies):
    with session_factory.begin() as session:
        user = User(name="Test User", email=f"user-{copies}-{id(session)}@example.com")
        book = Book(
            title="Test Book",
            author="Test Author",
            isbn=f"ISBN-{copies}-{id(session)}",
            total_copies=copies,
            available_copies=copies,
        )
        session.add_all([user, book])
        session.flush()
        reservation = Reservation(user_id=user.id, book_id=book.id, status="Pending")
        session.add(reservation)
        session.flush()
        reservation_id = reservation.id
    return reservation_id


def test_worker_reserves_a_copy_and_decrements_inventory():
    session_factory = make_session_factory()
    reservation_id = seed_reservation(session_factory, copies=1)

    with session_factory() as session:
        assert process_reservation(session, reservation_id) == "Reserved"
        reservation = session.get(Reservation, reservation_id)
        book = session.get(Book, reservation.book_id)
        assert reservation.status == "Reserved"
        assert book.available_copies == 0


def test_worker_rejects_when_no_copies_are_available():
    session_factory = make_session_factory()
    reservation_id = seed_reservation(session_factory, copies=0)

    with session_factory() as session:
        assert process_reservation(session, reservation_id) == "Rejected"
        reservation = session.get(Reservation, reservation_id)
        book = session.get(Book, reservation.book_id)
        assert reservation.status == "Rejected"
        assert book.available_copies == 0


def test_reprocessing_message_does_not_decrement_inventory_twice():
    session_factory = make_session_factory()
    reservation_id = seed_reservation(session_factory, copies=1)

    with session_factory() as session:
        process_reservation(session, reservation_id)
        assert process_reservation(session, reservation_id) == "Reserved"
        reservation = session.get(Reservation, reservation_id)
        book = session.get(Book, reservation.book_id)
        assert book.available_copies == 0


def test_borrow_and_return_transition_restore_inventory():
    session_factory = make_session_factory()
    reservation_id = seed_reservation(session_factory, copies=1)

    with session_factory() as session:
        process_reservation(session, reservation_id)
    with session_factory() as session:
        assert borrow_reservation(session, reservation_id).status == "Borrowed"
    with session_factory() as session:
        assert return_reservation(session, reservation_id).status == "Returned"
    with session_factory() as session:
        reservation = session.get(Reservation, reservation_id)
        book = session.get(Book, reservation.book_id)
        assert book.available_copies == 1
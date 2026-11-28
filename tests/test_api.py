import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app, get_session
from app.models import Book, Reservation, User
from app.services import process_reservation


def make_api_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session_factory


def test_health_and_books_api():
    client, session_factory = make_api_client()
    with session_factory.begin() as session:
        session.add(
            Book(
                title="Clean Code",
                author="Robert C. Martin",
                isbn="9780132350884",
                total_copies=1,
                available_copies=1,
            )
        )

    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/books?q=clean")
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Clean Code"

    availability = client.get("/books/1/availability")
    assert availability.status_code == 200
    assert availability.json()["available_copies"] == 1
    client.close()


def test_create_reservation_and_user_reservations_api():
    client, session_factory = make_api_client()
    with session_factory.begin() as session:
        session.add_all(
            [
                User(name="Nguyen Van An", email="an@example.com"),
                Book(
                    title="Dac nhan tam",
                    author="Dale Carnegie",
                    isbn="9780671027032",
                    total_copies=2,
                    available_copies=2,
                ),
            ]
        )

    response = client.post("/reservations", json={"user_id": 1, "book_id": 1})
    assert response.status_code == 202
    reservation_id = response.json()["id"]
    assert response.json()["status"] == "Pending"

    detail = client.get(f"/reservations/{reservation_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "Pending"

    user_reservations = client.get("/users/1/reservations")
    assert user_reservations.status_code == 200
    assert len(user_reservations.json()) == 1
    client.close()


def test_borrow_and_return_api_transition():
    client, session_factory = make_api_client()
    with session_factory.begin() as session:
        user = User(name="Test User", email="test@example.com")
        book = Book(
            title="Test Book",
            author="Test Author",
            isbn="TEST-ISBN",
            total_copies=1,
            available_copies=1,
        )
        session.add_all([user, book])
        session.flush()
        reservation = Reservation(user_id=user.id, book_id=book.id, status="Pending")
        session.add(reservation)
        session.flush()
        reservation_id = reservation.id

    with session_factory() as session:
        assert process_reservation(session, reservation_id) == "Reserved"

    borrow = client.post(f"/reservations/{reservation_id}/borrow")
    assert borrow.status_code == 200
    assert borrow.json()["status"] == "Borrowed"

    returned = client.post(f"/reservations/{reservation_id}/return")
    assert returned.status_code == 200
    assert returned.json()["status"] == "Returned"

    availability = client.get("/books/1/availability")
    assert availability.json()["available_copies"] == 1
    client.close()

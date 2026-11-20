from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Book, OutboxEvent, Reservation, User
from app.schemas import (
    BookCreate,
    BookRead,
    ReservationCreate,
    ReservationRead,
    UserCreate,
    UserRead,
)
from app.services import (
    InvalidReservationTransition,
    ReservationNotFound,
    borrow_reservation,
    return_reservation,
)


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as session:
        if session.scalar(select(User.id).limit(1)) is None:
            session.add_all(
                [
                    User(name="Nguyen Van An", email="an@example.com"),
                    User(name="Tran Thi Binh", email="binh@example.com"),
                ]
            )
        if session.scalar(select(Book.id).limit(1)) is None:
            session.add_all(
                [
                    Book(title="Dac nhan tam", author="Dale Carnegie", isbn="9780671027032", total_copies=3, available_copies=3),
                    Book(title="Nha gia kim", author="Paulo Coelho", isbn="9780062315007", total_copies=2, available_copies=2),
                    Book(title="Clean Code", author="Robert C. Martin", isbn="9780132350884", total_copies=1, available_copies=1),
                ]
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="He thong thu vien va dat muon sach phan tan",
    version="1.0.0",
    description="REST API, PostgreSQL va RabbitMQ worker cho quy trinh dat muon sach.",
    lifespan=lifespan,
)


def get_session():
    with SessionLocal() as session:
        yield session


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/books", response_model=list[BookRead])
def list_books(
    q: str | None = Query(default=None, description="Tim theo ten sach, tac gia hoac ISBN"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    statement = select(Book).order_by(Book.id).offset(offset).limit(limit)
    if q:
        pattern = f"%{q}%"
        statement = statement.where(or_(Book.title.ilike(pattern), Book.author.ilike(pattern), Book.isbn.ilike(pattern)))
    return session.scalars(statement).all()


@app.post("/books", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, session: Session = Depends(get_session)):
    book = Book(**payload.model_dump(), available_copies=payload.total_copies)
    session.add(book)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="ISBN da ton tai")
    session.refresh(book)
    return book


@app.get("/books/{book_id}", response_model=BookRead)
def get_book(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Khong tim thay sach")
    return book


@app.get("/books/{book_id}/availability")
def get_book_availability(book_id: int, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Khong tim thay sach")
    return {"book_id": book.id, "available": book.available_copies > 0, "available_copies": book.available_copies}


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    user = User(**payload.model_dump())
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Email da duoc su dung")
    session.refresh(user)
    return user


@app.post("/reservations", response_model=ReservationRead, status_code=status.HTTP_202_ACCEPTED)
def create_reservation(payload: ReservationCreate, session: Session = Depends(get_session)):
    if session.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="Khong tim thay nguoi dung")
    if session.get(Book, payload.book_id) is None:
        raise HTTPException(status_code=404, detail="Khong tim thay sach")

    reservation = Reservation(user_id=payload.user_id, book_id=payload.book_id, status="Pending")
    session.add(reservation)
    session.flush()
    session.add(OutboxEvent(reservation_id=reservation.id))
    session.commit()
    session.refresh(reservation)
    return reservation


@app.get("/reservations/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: int, session: Session = Depends(get_session)):
    reservation = session.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Khong tim thay yeu cau dat muon")
    return reservation


@app.get("/users/{user_id}/reservations", response_model=list[ReservationRead])
def list_user_reservations(user_id: int, session: Session = Depends(get_session)):
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="Khong tim thay nguoi dung")
    statement = select(Reservation).where(Reservation.user_id == user_id).order_by(Reservation.created_at.desc())
    return session.scalars(statement).all()


def update_reservation_status(reservation_id: int, action: str, session: Session):
    try:
        reservation = borrow_reservation(session, reservation_id) if action == "borrow" else return_reservation(session, reservation_id)
    except ReservationNotFound:
        raise HTTPException(status_code=404, detail="Khong tim thay yeu cau dat muon")
    except InvalidReservationTransition:
        raise HTTPException(status_code=409, detail="Trang thai hien tai khong cho phep thao tac nay")
    return reservation


@app.post("/reservations/{reservation_id}/borrow", response_model=ReservationRead)
def borrow_book(reservation_id: int, session: Session = Depends(get_session)):
    return update_reservation_status(reservation_id, "borrow", session)


@app.post("/reservations/{reservation_id}/return", response_model=ReservationRead)
def return_book(reservation_id: int, session: Session = Depends(get_session)):
    return update_reservation_status(reservation_id, "return", session)
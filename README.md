# He thong thu vien va dat muon sach phan tan

Du an mau theo De tai 20, gom REST API (FastAPI), PostgreSQL, RabbitMQ va worker xu ly yeu cau dat muon bat dong bo.

## Chay toan bo bang Docker

Can cai Docker Desktop va bat Docker Engine. Tai thu muc du an, chay:

```bash
docker compose up --build
```

API: <http://localhost:8000>  
Swagger UI: <http://localhost:8000/docs>  
RabbitMQ Management: <http://localhost:15672> (tai khoan `library`, mat khau `library`)

Du lieu thu nghiem duoc tao khi API khoi dong: hai nguoi dung (ID 1, 2) va ba dau sach (ID 1-3). API va worker dung chung PostgreSQL. Yeu cau dat muon duoc ghi cung outbox trong mot giao dich, sau do worker day vao RabbitMQ va cap nhat trang thai.

## Chuc nang

- Tim danh sach sach theo ten, tac gia, ISBN; xem chi tiet va so ban con.
- Tao sach va nguoi dung.
- Gui yeu cau dat muon; trang thai ban dau la `Pending`.
- Worker kiem tra ton kho, giam so ban con va chuyen sang `Reserved`, hoac chuyen sang `Rejected` neu het sach.
- Tra cuu trang thai yeu cau va danh sach yeu cau cua mot nguoi dung.
- Chuyen `Reserved` sang `Borrowed`; chuyen `Borrowed` sang `Returned` va cong lai ton kho.
- Outbox giup khong that lac yeu cau neu RabbitMQ tam thoi mat ket noi; xu ly message co tinh idempotent.

Trang thai hop le: `Pending`, `Reserved`, `Rejected`, `Borrowed`, `Returned`.

## API chinh

| Method | Endpoint | Mo ta |
| --- | --- | --- |
| GET | `/books?q=clean` | Tim sach |
| GET | `/books/{id}` | Chi tiet sach va ton kho |
| GET | `/books/{id}/availability` | Kiem tra kha dung |
| POST | `/books` | Them sach |
| POST | `/users` | Tao nguoi dung |
| POST | `/reservations` | Gui yeu cau dat muon (202 Accepted) |
| GET | `/reservations/{id}` | Xem trang thai yeu cau |
| GET | `/users/{userId}/reservations` | Danh sach yeu cau cua nguoi dung |
| POST | `/reservations/{id}/borrow` | Xac nhan da muon |
| POST | `/reservations/{id}/return` | Xac nhan da tra |

## Thu nhanh

Tao yeu cau dat sach dau tien cho nguoi dung dau tien:

```bash
curl -X POST http://localhost:8000/reservations \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"book_id":1}'
```

Phan hoi tra ve ma yeu cau va trang thai `Pending`. Worker xu ly bat dong bo; goi `GET /reservations/{id}` de xem ket qua. Khi da `Reserved`, co the goi endpoint `/borrow`, sau do `/return`.

## Chay test nghiep vu

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Test bao phu dat thanh cong, het ton va xu ly message lap lai. Docker Compose la cach chay day du ca PostgreSQL va RabbitMQ.
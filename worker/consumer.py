import json
import logging
import threading
import time

import pika
from sqlalchemy import select

from app.config import RABBITMQ_URL, RESERVATION_QUEUE
from app.db import Base, SessionLocal, engine
from app.models import OutboxEvent
from app.services import process_reservation


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def connect_rabbitmq():
    parameters = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=RESERVATION_QUEUE, durable=True)
    return connection, channel


def dispatch_outbox() -> None:
    while True:
        try:
            with SessionLocal() as session:
                events = session.scalars(
                    select(OutboxEvent).where(OutboxEvent.dispatched.is_(False)).order_by(OutboxEvent.id).limit(50)
                ).all()
                for event in events:
                    connection, channel = connect_rabbitmq()
                    channel.confirm_delivery()
                    channel.basic_publish(
                        exchange="",
                        routing_key=RESERVATION_QUEUE,
                        body=json.dumps({"reservation_id": event.reservation_id}),
                        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
                    )
                    connection.close()
                    event.dispatched = True
                if events:
                    session.commit()
        except Exception:
            logger.exception("Khong the day outbox vao RabbitMQ; se thu lai")
        time.sleep(1)


def handle_message(channel, method, properties, body) -> None:
    try:
        payload = json.loads(body)
        reservation_id = int(payload["reservation_id"])
        with SessionLocal() as session:
            result = process_reservation(session, reservation_id)
        logger.info("Yeu cau #%s duoc xu ly: %s", reservation_id, result)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        logger.exception("Xu ly yeu cau dat muon that bai")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def consume_forever() -> None:
    while True:
        connection = None
        try:
            connection, channel = connect_rabbitmq()
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RESERVATION_QUEUE, on_message_callback=handle_message)
            logger.info("Worker dang lang nghe queue %s", RESERVATION_QUEUE)
            channel.start_consuming()
        except Exception:
            logger.exception("Mat ket noi RabbitMQ; se ket noi lai")
            time.sleep(3)
        finally:
            if connection is not None and connection.is_open:
                connection.close()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    threading.Thread(target=dispatch_outbox, daemon=True).start()
    consume_forever()


if __name__ == "__main__":
    main()
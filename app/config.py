import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://library:library@localhost:5432/library",
)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
RESERVATION_QUEUE = "reservation_requests"
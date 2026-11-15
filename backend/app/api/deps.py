from fastapi import Header

from app.services.learning import check_client


def client_id_required(x_client_id: str | None = Header(default=None)) -> str:
    return check_client(x_client_id)


def client_id_optional(x_client_id: str | None = Header(default=None)) -> str | None:
    return x_client_id if x_client_id else None

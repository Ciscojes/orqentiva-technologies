"""Servicios y horario del negocio autenticado; reservas de solo lectura."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select, delete

from app.deps import Database, Tenant
from app.models import BusinessHours, Service
from app.scheduling import require_agenda
from app.schemas import WeekIn
from app.services.agenda import to_minutes
from app.services.dashboard import business_dashboard, hours_view, service_view

router = APIRouter(prefix="/client", tags=["client"])


class ServiceIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=150)
    price_crc: int = Field(ge=0, le=10000000, strict=True)
    duration_minutes: int = Field(ge=5, le=480, strict=True)
    is_active: StrictBool = True


@router.get("/dashboard")
def dashboard(business_id: Tenant, session: Database):
    return business_dashboard(session, business_id)


@router.post("/services", status_code=201)
def add_service(payload: ServiceIn, business_id: Tenant, session: Database):
    require_agenda(session, business_id, lock=True)
    service = Service(business_id=business_id, **payload.model_dump())
    session.add(service)
    session.commit()
    return service_view(service)


@router.put("/services/{service_id}")
def edit_service(service_id: int, payload: ServiceIn, business_id: Tenant, session: Database):
    require_agenda(session, business_id, lock=True)
    service = session.scalar(select(Service).where(Service.id == service_id, Service.business_id == business_id))
    if service is None:
        raise HTTPException(404, "Servicio no encontrado")
    for key, value in payload.model_dump().items():
        setattr(service, key, value)
    session.commit()
    return service_view(service)


@router.put("/hours")
def save_hours(payload: WeekIn, business_id: Tenant, session: Database):
    require_agenda(session, business_id, lock=True)
    session.execute(delete(BusinessHours).where(BusinessHours.business_id == business_id))
    rows = [BusinessHours(business_id=business_id, weekday=day.weekday, is_closed=day.is_closed,
                          opens_at=to_minutes(day.opens_at), closes_at=to_minutes(day.closes_at)) for day in payload.days]
    session.add_all(rows)
    session.commit()
    return hours_view(rows)

"""Datos del panel de un negocio: catálogo, horario, equipo y reservas.

Lo usan el panel del negocio (/client/dashboard) y la ficha del negocio en
administración (/admin/businesses/{id}/dashboard, solo lectura).
"""
from datetime import timezone

from sqlalchemy import select

from app.models import Appointment, Business, BusinessHours, Professional, Service
from app.scheduling import utc
from app.services.agenda import to_clock

TIME_ZONE = "America/Costa_Rica"


def service_view(row: Service):
    return {"id": row.id, "name": row.name, "price_crc": row.price_crc,
            "duration_minutes": row.duration_minutes, "is_active": row.is_active}


def hours_view(rows):
    by_day = {row.weekday: row for row in rows}
    return {"configured": len(by_day) == 7, "days": [
        {"weekday": day, "is_closed": by_day[day].is_closed if day in by_day else True,
         "opens_at": to_clock(by_day[day].opens_at) if day in by_day else None,
         "closes_at": to_clock(by_day[day].closes_at) if day in by_day else None}
        for day in range(7)]}


def business_dashboard(session, business_id: str):
    """Lo que ve el negocio en su panel; administración lo consulta en solo lectura."""
    business = session.get(Business, business_id)
    if not business.booking_enabled:
        return {"booking_enabled": False, "business": {"id": business.id, "name": business.name, "time_zone": TIME_ZONE}}
    team = session.scalars(select(Professional).where(Professional.business_id == business_id).order_by(Professional.id)).all()
    services = session.scalars(select(Service).where(Service.business_id == business_id).order_by(Service.id))
    appointments = session.scalars(select(Appointment).where(Appointment.business_id == business_id)
                                   .order_by(Appointment.starts_at, Appointment.id))
    bookings = []
    for row in appointments:
        stamp = row.starts_at if row.starts_at.tzinfo else row.starts_at.replace(tzinfo=timezone.utc)
        bookings.append({"id": row.id, "customer_name": row.customer_name, "customer_contact": row.customer_contact,
                         "starts_at": stamp.astimezone(timezone.utc).isoformat()})
        if row.professional_id is not None:
            bookings[-1].update(professional_id=row.professional_id, service_id=row.service_id, ends_at=utc(row.ends_at).isoformat())
    hours = session.scalars(select(BusinessHours).where(BusinessHours.business_id == business_id)).all()
    return {"booking_enabled": True, "team": [{"id": p.id, "name": p.name, "service_ids": p.service_ids, "days": p.days} for p in team], "business": {"id": business.id, "name": business.name, "time_zone": TIME_ZONE},
            "services": [service_view(row) for row in services], "appointments": bookings, "hours": hours_view(hours)}

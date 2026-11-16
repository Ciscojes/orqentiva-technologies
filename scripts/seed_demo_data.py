r"""Datos de demostración para el entorno de desarrollo (PostgreSQL local, puerto 5178).

Uso:  python scripts/seed_demo_data.py
      (o .\scripts\iniciar.ps1 -Demo, que lo ejecuta después de las migraciones)

Crea, solo si no existen, los negocios alfa y beta con servicios, horario, trabajadores,
citas futuras y base de conocimiento, y las cuentas de prueba del README. Se puede repetir:
no duplica nada ni modifica tus datos. La única excepción son las tres cuentas de prueba
@example.com: se reactivan y vuelven a tener la contraseña de demostración, para que siempre
puedas entrar durante una presentación.

Se niega a ejecutarse contra una base que no sea local, para que la contraseña pública de
demostración nunca llegue a un servidor real.
"""
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

DEMO_PASSWORD = "Orqentiva-Demo-2026!"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
ZONE = ZoneInfo("America/Costa_Rica")
ACCOUNTS = [("admin@example.com", "super_admin", None), ("alfa@example.com", "business_admin", "alfa"),
            ("beta@example.com", "business_admin", "beta")]
SERVICES = {
    "alfa": [("Corte demo", 5000, 30), ("Barba", 4000, 20), ("Tinte", 18000, 90)],
    "beta": [("Corte demo", 8500, 30), ("Afeitado clásico", 6000, 30)],
}
TEAM = {"alfa": ["Ana", "Sofía"], "beta": ["Luis"]}
CUSTOMERS = {"alfa": ["Carlos Mora", "Laura Pérez", "Diego Rojas", "María Solís"], "beta": ["Andrés Vargas", "Paula Jiménez"]}
DOCUMENTS = [
    ("Cancelaciones", "Para cancelar o reprogramar una cita, avisa con al menos {hours} horas de anticipación.\n\n"
     "Si llegas más de 15 minutos tarde, es posible que debamos reprogramar tu cita.", True),
    ("Formas de pago", "Puedes pagar con efectivo, tarjeta o SINPE Móvil al terminar el servicio.\n\n"
     "No pedimos depósito para reservar.", True),
    ("Ubicación y parqueo", "Estamos en San José centro, 100 metros al norte del parque central.\n\n"
     "Hay parqueo gratuito frente al local.", False),
]


def is_local(url) -> bool:
    return url.get_backend_name() == "sqlite" or (url.host or "") in LOCAL_HOSTS


def week(opens="09:00", closes="18:00"):
    """Lunes a sábado abierto; domingo cerrado (weekday 0 = lunes)."""
    return [{"weekday": d, "is_closed": d == 6, "opens_at": None if d == 6 else opens,
             "closes_at": None if d == 6 else closes} for d in range(7)]


def next_workdays(count, today):
    day, found = today, []
    while len(found) < count:
        day += timedelta(days=1)
        if day.weekday() != 6:
            found.append(day)
    return found


def seed_demo(session_factory, engine_url, now=None):
    from app.auth import UserCreate, create_user, password_hasher
    from app.models import (Appointment, BusinessHours, KnowledgeDocument, Professional, Service,
                            User)
    from seed import seed_database

    if not is_local(engine_url):
        raise SystemExit("La base de datos no es local. No se cargan datos de demostración en un servidor.")
    seed_database(session_factory)
    now = now or datetime.now(ZONE)
    summary = []
    with session_factory.begin() as session:
        for business_id, services in SERVICES.items():
            for name, price, minutes in services:
                if session.scalar(select(Service.id).where(Service.business_id == business_id, Service.name == name)) is None:
                    session.add(Service(business_id=business_id, name=name, price_crc=price, duration_minutes=minutes))
                    summary.append(f"{business_id}: servicio {name}")
            session.flush()
            timed = list(session.scalars(select(Service).where(Service.business_id == business_id,
                                                               Service.duration_minutes.is_not(None)).order_by(Service.id)))
            if session.scalar(select(func.count()).select_from(BusinessHours).where(BusinessHours.business_id == business_id)) == 0:
                for day in week():
                    session.add(BusinessHours(business_id=business_id, weekday=day["weekday"], is_closed=day["is_closed"],
                                              opens_at=None if day["is_closed"] else 540,
                                              closes_at=None if day["is_closed"] else 1080))
                summary.append(f"{business_id}: horario")
            team = list(session.scalars(select(Professional).where(Professional.business_id == business_id)))
            if not team:
                for name in TEAM[business_id]:
                    member = Professional(business_id=business_id, name=name, days=week(),
                                          service_ids=[s.id for s in timed])
                    session.add(member)
                    team.append(member)
                session.flush()
                summary.append(f"{business_id}: trabajadores {', '.join(TEAM[business_id])}")
            future = session.scalar(select(func.count()).select_from(Appointment).where(
                Appointment.business_id == business_id, Appointment.starts_at >= now))
            if future == 0 and team and timed:
                days = next_workdays(2, now.date())
                for index, customer in enumerate(CUSTOMERS[business_id]):
                    service = timed[index % len(timed)]
                    member = team[index % len(team)]
                    start = datetime.combine(days[index // 2 % 2], time(9 + index, 0), ZONE)
                    session.add(Appointment(business_id=business_id, customer_name=customer, starts_at=start,
                                            ends_at=start + timedelta(minutes=service.duration_minutes),
                                            professional_id=member.id, service_id=service.id,
                                            customer_contact="8888-0000"))
                summary.append(f"{business_id}: {len(CUSTOMERS[business_id])} citas de ejemplo")
            if session.scalar(select(func.count()).select_from(KnowledgeDocument).where(
                    KnowledgeDocument.business_id == business_id)) == 0:
                for title, body, published in DOCUMENTS:
                    session.add(KnowledgeDocument(business_id=business_id, title=title, published=published,
                                                  body=body.format(hours=24 if business_id == "alfa" else 48)))
                summary.append(f"{business_id}: base de conocimiento")
        for email, role, business_id in ACCOUNTS:
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                create_user(session, UserCreate(email=email, password=DEMO_PASSWORD, role=role, business_id=business_id))
                summary.append(f"cuenta {email}")
            elif user.role == role and user.business_id == business_id:
                user.password_hash = password_hasher.hash(DEMO_PASSWORD)
                user.is_active = True
            else:
                summary.append(f"AVISO: {email} ya existe con otro rol; no se modificó")
    return summary


def main():
    from app.database import SessionLocal, engine
    try:
        summary = seed_demo(SessionLocal, engine.url)
    finally:
        engine.dispose()
    print("Datos de demostración listos." + ("" if summary else " No hacía falta crear nada nuevo."))
    for line in summary:
        print("  -", line)
    print("Cuentas de prueba (contraseña " + DEMO_PASSWORD + "):")
    for email, role, business_id in ACCOUNTS:
        print(f"  - {email} ({'administración' if role == 'super_admin' else 'negocio ' + business_id})")


if __name__ == "__main__":
    main()

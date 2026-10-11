import uuid
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import EngineeringEvent, AuditLog


class DuplicateDeliveryConflict(Exception):
    """A delivery ID was reused for different content or a different project."""


def same_delivery(event, project_id, event_type, payload):
    if event.project_id != project_id or event.event_type != event_type or event.payload != payload:
        raise DuplicateDeliveryConflict()
    return event, False


def ingest(db, project, source, delivery_id, event_type, payload, actor_id=None):
    delivery_id = delivery_id or str(uuid.uuid4())
    project_id = project.id
    lookup = select(EngineeringEvent).where(
        EngineeringEvent.source == source, EngineeringEvent.delivery_id == delivery_id)
    existing = db.scalar(lookup)
    if existing:
        return same_delivery(existing, project_id, event_type, payload)
    event = EngineeringEvent(project_id=project_id, source=source, delivery_id=delivery_id,
                             event_type=event_type, payload=payload)
    db.add(event)
    db.add(AuditLog(organization_id=project.organization_id, actor_id=actor_id, action='event.ingested',
                   details={'source': source, 'delivery_id': delivery_id}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(lookup)
        if existing is None:
            # Do not turn unrelated database constraint failures into duplicate success.
            raise
        return same_delivery(existing, project_id, event_type, payload)
    return event, True


def retry_delay(attempt):
    return timedelta(seconds=min(300, 2 ** attempt))

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints
from sqlalchemy import func, select

from app.access_routes import PageNumber, PageSize
from app.auth.routes import Authenticated, Database, require_permission
from app.auth.scopes import customer_scope, task_scope
from app.db.models import CustomerAssignment, CustomerStatus, FollowupRecord, FollowupTask, Member, OperationLog, StaffProfile
from app.directory import Page, count_rows
from app.http import APIError, SuccessEnvelope, success

router = APIRouter(prefix="/api/v1", tags=["followups"])
Customer = Annotated[Authenticated, Depends(require_permission("R6"))]
TaskUser = Annotated[Authenticated, Depends(require_permission("R8"))]
TaskCreator = Annotated[Authenticated, Depends(require_permission("R9"))]
Management = Annotated[Authenticated, Depends(require_permission("R11"))]
Contact = Literal["phone", "wechat", "home_visit", "store_visit", "other"]
Status = Literal["pending", "postponed", "completed", "ignored"]
TaskType = Literal["recall", "reactivation", "manual"]
Nonblank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\x00]+$")]
From = Annotated[AwareDatetime | None, Query(alias="from")]


class FollowupInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_type: Contact
    content: Nonblank
    followup_at: AwareDatetime | None = None
    customer_feedback: Nonblank | None = None
    effective_contact: bool = False
    gift_given: bool = False
    gift_name: Annotated[Nonblank, StringConstraints(max_length=120)] | None = None
    next_followup_at: AwareDatetime | None = None


class FollowupView(FollowupInput):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_id: UUID
    staff_id: UUID
    followup_at: AwareDatetime


class AdminFollowupView(FollowupView):
    member_name: str
    staff_name: str


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    assigned_staff_id: UUID
    title: Annotated[Nonblank, StringConstraints(max_length=120)]
    scheduled_at: AwareDatetime


class TaskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_id: UUID
    assigned_staff_id: UUID | None
    member_name: str
    staff_name: str | None
    task_type: TaskType
    status: Status
    title: str
    scheduled_at: AwareDatetime
    postponed_until: AwareDatetime | None
    planned_at: AwareDatetime
    result: str | None
    completed_at: AwareDatetime | None


class TaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Nonblank


class PostponeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    postponed_until: AwareDatetime
    result: Nonblank | None = None


def lock_member(db: Database, member_id: UUID) -> None:
    if db.scalar(select(Member.id).where(Member.id == member_id).with_for_update()) is None:
        raise APIError(404, "NOT_FOUND", "客户不存在")


def visible_customer(db: Database, member_id: UUID, session: Authenticated) -> None:
    if db.scalar(select(Member.id).where(Member.id == member_id, customer_scope(session.identity))) is None:
        raise APIError(404, "NOT_FOUND", "客户不存在或已不在当前负责范围")


def audit(db: Database, request: Request, session: Authenticated, action: str, target_id: UUID,
          target_type: str, after: dict[str, str], before: dict[str, str] | None = None) -> None:
    db.add(OperationLog(
        actor_account_id=session.identity.account_id, actor_role=session.identity.selected_role or "unknown",
        module="followups", action=action, target_type=target_type, target_id=target_id,
        request_id=request.state.request_id, before_data=before, after_data=after,
    ))


def utc_fields(values: dict, *keys: str) -> dict:
    return {**values, **{key: values[key].astimezone(UTC) for key in keys if values[key] is not None}}


def followup_view(row: FollowupRecord) -> FollowupView:
    values = FollowupView.model_validate(row).model_dump()
    return FollowupView(**utc_fields(values, "followup_at", "next_followup_at"))


def task_view(row: FollowupTask, member_name: str, staff_name: str | None) -> TaskView:
    values = TaskView.model_validate({
        **{name: getattr(row, name) for name in TaskView.model_fields if name not in ("member_name", "staff_name", "planned_at")},
        "member_name": member_name, "staff_name": staff_name, "planned_at": row.postponed_until or row.scheduled_at,
    }).model_dump()
    return TaskView(**utc_fields(values, "scheduled_at", "postponed_until", "planned_at", "completed_at"))


def validate_range(start: datetime | None, end: datetime | None) -> None:
    if start is not None and end is not None and start >= end:
        raise APIError(422, "INVALID_TIME_RANGE", "开始时间必须早于结束时间")


@router.get("/customers/{id}/followups", response_model=SuccessEnvelope[Page[FollowupView]])
def customer_followups(request: Request, id: UUID, db: Database, session: Customer,
                       page: PageNumber = 1, page_size: PageSize = 20,
                       contact_type: Contact | None = None, start: From = None, to: AwareDatetime | None = None):
    visible_customer(db, id, session)
    validate_range(start, to)
    query = select(FollowupRecord).join(Member, Member.id == FollowupRecord.member_id).where(
        FollowupRecord.member_id == id, customer_scope(session.identity),
    )
    if contact_type is not None:
        query = query.where(FollowupRecord.contact_type == contact_type)
    if start is not None:
        query = query.where(FollowupRecord.followup_at >= start)
    if to is not None:
        query = query.where(FollowupRecord.followup_at < to)
    total = count_rows(db, query)
    rows = db.scalars(query.order_by(FollowupRecord.followup_at.desc(), FollowupRecord.id.desc())
                      .offset((page - 1) * page_size).limit(page_size))
    return success(request, Page[FollowupView](items=[followup_view(row) for row in rows], page=page, page_size=page_size, total=total))


@router.post("/customers/{id}/followups", status_code=201, response_model=SuccessEnvelope[FollowupView])
def create_followup(request: Request, id: UUID, body: FollowupInput, db: Database, session: Customer):
    lock_member(db, id)
    visible_customer(db, id, session)
    staff_id = db.scalar(select(StaffProfile.id).where(
        StaffProfile.account_id == session.identity.account_id, StaffProfile.role == session.identity.selected_role,
        StaffProfile.status == "active", StaffProfile.disabled_at.is_(None),
    ).with_for_update(read=True))
    if staff_id is None:
        raise APIError(401, "INVALID_SESSION", "当前会话已失效")
    row = FollowupRecord(
        member_id=id, staff_id=staff_id, created_by_account_id=session.identity.account_id,
        **body.model_dump(exclude={"followup_at"}), followup_at=body.followup_at or datetime.now(UTC),
    )
    db.add(row)
    if body.effective_contact:
        state = db.scalar(select(CustomerStatus).where(CustomerStatus.member_id == id).with_for_update())
        if state is not None and (state.last_effective_contact_at is None or row.followup_at > state.last_effective_contact_at):
            state.last_effective_contact_at = row.followup_at
            state.updated_by_account_id = session.identity.account_id
            state.updated_at = datetime.now(UTC)
    db.flush()
    audit(db, request, session, "followup_create", row.id, "followup_record", {"contact_type": body.contact_type})
    result = followup_view(row)
    db.commit()
    return success(request, result, status=201)


@router.get("/admin/followups", response_model=SuccessEnvelope[Page[AdminFollowupView]])
def admin_followups(request: Request, db: Database, session: Management, page: PageNumber = 1, page_size: PageSize = 20,
                    member_id: UUID | None = None, staff_id: UUID | None = None, contact_type: Contact | None = None,
                    start: From = None, to: AwareDatetime | None = None):
    validate_range(start, to)
    query = select(FollowupRecord, Member.name, StaffProfile.display_name).join(
        Member, Member.id == FollowupRecord.member_id,
    ).join(StaffProfile, StaffProfile.id == FollowupRecord.staff_id)
    for column, value in ((FollowupRecord.member_id, member_id), (FollowupRecord.staff_id, staff_id),
                          (FollowupRecord.contact_type, contact_type)):
        if value is not None:
            query = query.where(column == value)
    if start is not None:
        query = query.where(FollowupRecord.followup_at >= start)
    if to is not None:
        query = query.where(FollowupRecord.followup_at < to)
    total = count_rows(db, query)
    rows = db.execute(query.order_by(FollowupRecord.followup_at.desc(), FollowupRecord.id.desc())
                      .offset((page - 1) * page_size).limit(page_size))
    items = [AdminFollowupView(**followup_view(row).model_dump(), member_name=name, staff_name=staff) for row, name, staff in rows]
    return success(request, Page[AdminFollowupView](items=items, page=page, page_size=page_size, total=total))


@router.get("/followup-tasks", response_model=SuccessEnvelope[Page[TaskView]])
def list_tasks(request: Request, db: Database, session: TaskUser, page: PageNumber = 1, page_size: PageSize = 20,
               status: Status | None = None, task_type: TaskType | None = None, assigned_staff_id: UUID | None = None,
               start: From = None, to: AwareDatetime | None = None):
    validate_range(start, to)
    planned = func.coalesce(FollowupTask.postponed_until, FollowupTask.scheduled_at)
    query = select(FollowupTask, Member.name, StaffProfile.display_name).join(
        Member, Member.id == FollowupTask.member_id,
    ).outerjoin(StaffProfile, StaffProfile.id == FollowupTask.assigned_staff_id).where(task_scope(session.identity))
    for column, value in ((FollowupTask.status, status), (FollowupTask.task_type, task_type),
                          (FollowupTask.assigned_staff_id, assigned_staff_id)):
        if value is not None:
            query = query.where(column == value)
    if start is not None:
        query = query.where(planned >= start)
    if to is not None:
        query = query.where(planned < to)
    total = count_rows(db, query)
    rows = db.execute(query.order_by(planned.desc(), FollowupTask.id.desc())
                      .offset((page - 1) * page_size).limit(page_size))
    items = [task_view(row, name, staff) for row, name, staff in rows]
    return success(request, Page[TaskView](items=items, page=page, page_size=page_size, total=total))


@router.post("/followup-tasks", status_code=201, response_model=SuccessEnvelope[TaskView])
def create_task(request: Request, body: TaskInput, db: Database, session: TaskCreator):
    lock_member(db, body.member_id)
    current = db.scalar(select(CustomerAssignment.staff_id).where(
        CustomerAssignment.member_id == body.member_id, CustomerAssignment.is_current.is_(True),
    ))
    if current != body.assigned_staff_id:
        raise APIError(409, "ASSIGNMENT_CHANGED", "请选择客户当前负责人")
    row = FollowupTask(
        **body.model_dump(), task_type="manual", status="pending", dedupe_key=f"manual:{uuid4()}",
        created_by_account_id=session.identity.account_id,
    )
    db.add(row)
    db.flush()
    audit(db, request, session, "task_create", row.id, "followup_task", {"status": row.status})
    result = task_view(row, db.get_one(Member, row.member_id).name, db.get_one(StaffProfile, current).display_name)
    db.commit()
    return success(request, result, status=201)


def update_task(request: Request, id: UUID, db: Database, session: Authenticated,
                status: Status, result: str | None, postponed_until: datetime | None = None):
    member_id = db.scalar(select(FollowupTask.member_id).where(FollowupTask.id == id, task_scope(session.identity)))
    if member_id is None:
        raise APIError(404, "NOT_FOUND", "任务不存在或已不在当前负责范围")
    lock_member(db, member_id)
    row = db.scalar(select(FollowupTask).where(FollowupTask.id == id, task_scope(session.identity)).with_for_update())
    if row is None:
        raise APIError(404, "NOT_FOUND", "任务不存在或已不在当前负责范围")
    if row.status in ("completed", "ignored"):
        raise APIError(409, "TASK_TERMINAL", "任务已结束，不能再次修改")
    previous = {"status": row.status}
    row.status = status
    if result is not None:
        row.result = result
    row.updated_at = datetime.now(UTC)
    if postponed_until is not None:
        row.postponed_until = postponed_until
    if status == "completed":
        row.completed_at = row.updated_at
    changed: dict[str, str] = {"status": status}
    if postponed_until is not None:
        changed["postponed_until"] = postponed_until.astimezone(UTC).isoformat()
    audit(db, request, session, "task_" + status, row.id, "followup_task", changed, previous)
    staff = db.get(StaffProfile, row.assigned_staff_id) if row.assigned_staff_id else None
    view = task_view(row, db.get_one(Member, member_id).name, staff.display_name if staff else None)
    db.commit()
    return success(request, view)


@router.post("/followup-tasks/{id}/complete", response_model=SuccessEnvelope[TaskView])
def complete_task(request: Request, id: UUID, body: TaskResult, db: Database, session: TaskUser):
    return update_task(request, id, db, session, "completed", body.result)


@router.post("/followup-tasks/{id}/postpone", response_model=SuccessEnvelope[TaskView])
def postpone_task(request: Request, id: UUID, body: PostponeInput, db: Database, session: TaskUser):
    return update_task(request, id, db, session, "postponed", body.result, body.postponed_until)


@router.post("/followup-tasks/{id}/ignore", response_model=SuccessEnvelope[TaskView])
def ignore_task(request: Request, id: UUID, body: TaskResult, db: Database, session: TaskUser):
    return update_task(request, id, db, session, "ignored", body.result)

"""Run the 2.6.4 preview with synthetic data on ephemeral test containers."""
import json
import os
import secrets
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from redis import Redis
from sqlalchemy.orm import Session

from app.auth.sessions import SessionService
from app.config import AuthSettings
from app.db.models import CustomerAssignment, FollowupRecord, FollowupTask, Member, StaffProfile
from app.db.session import get_db
from app.main import app
from test_auth import add_login_account, isolated_auth_services
from test_permissions import add_employee, add_member


def run(root: Path, preview: Path) -> None:
    preview.mkdir(parents=True, exist_ok=False)
    os.environ.update(
        REDIS_HOST="127.0.0.1", REDIS_DB="0", REDIS_PASSWORD="",
        WECHAT_APP_ID="", WECHAT_APP_SECRET="",
        PHONE_ENCRYPTION_KEY=secrets.token_urlsafe(32) + "=",
        PHONE_LOOKUP_HMAC_KEY=secrets.token_urlsafe(32) + "=",
        AUTH_ACCESS_TTL_SECONDS="900", AUTH_SESSION_TTL_SECONDS="28800",
    )
    infrastructure = isolated_auth_services()
    try:
        engine, redis_port = next(infrastructure)
        os.environ["REDIS_PORT"] = str(redis_port)
        settings = AuthSettings(_env_file=None)

        def preview_db():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = preview_db
        app.state.auth_settings = settings
        credentials = {}
        for role in ("admin", "manager"):
            _, username, password = add_login_account(engine, role=role)
            credentials[role] = {"username": username, "password": password}

        with Session(engine) as db:
            first, staff_a = add_employee(db)
            second, staff_b = add_employee(db)
            db.get_one(StaffProfile, staff_a).display_name = "验收员工甲"
            db.get_one(StaffProfile, staff_b).display_name = "验收员工乙"
            for member_name, owner in (("验收客户甲", staff_a), ("验收客户乙", staff_a), ("验收客户丙", staff_b)):
                member = add_member(db)
                db.get_one(Member, member).name = member_name
                staff = db.get_one(StaffProfile, owner)
                db.add(CustomerAssignment(member_id=member, staff_id=owner, bind_source="manual"))
                db.add(FollowupRecord(
                    member_id=member, staff_id=owner, created_by_account_id=staff.account_id,
                    content="验收示例运营沟通", contact_type="phone", followup_at=datetime.now(UTC),
                ))
                for label, day in (("任务一", 1), ("任务二", 2)):
                    db.add(FollowupTask(
                        member_id=member, assigned_staff_id=owner, title=member_name + label, task_type="manual",
                        scheduled_at=datetime.now(UTC) + timedelta(days=day), dedupe_key=secrets.token_hex(16),
                    ))
            db.commit()

        with Redis(host="127.0.0.1", port=redis_port, decode_responses=True) as cache:
            sessions = SessionService(cache, settings)
            employees = {}
            for key, account in (("a", first), ("b", second)):
                pair = sessions.issue(account, "employee", "miniprogram")
                employees[key] = {"access_token": pair.access_token, "refresh_token": pair.refresh_token}
        mini = preview / "miniprogram"
        shutil.copytree(root / "miniprogram", mini, ignore=shutil.ignore_patterns(
            "node_modules", "project.private.config.json", ".env*", "tests",
        ))
        env = mini / "config" / "environment.ts"
        env.write_text(env.read_text(encoding="utf-8").replace("127.0.0.1:18081", "127.0.0.1:18164"), encoding="utf-8")
        app_ts = mini / "app.ts"
        source = app_ts.read_text(encoding="utf-8-sig").replace(
            "import { employeeSignedIn }", "import { employeeSignedIn, setStaffCustomerSession }",
        )
        app_ts.write_text(source.replace("App({", f"""const fixtures = {json.dumps(employees)} as const;

App({{
  onLaunch({{ query }}) {{
    const fixture = query.staff === 'b' ? fixtures.b : fixtures.a;
    setStaffCustomerSession({{ ...fixture, selected_role: 'employee' }});
  }},"""), encoding="utf-8")
        (preview / "credentials.local.json").write_text(json.dumps(credentials, indent=2), encoding="utf-8")
        print(f"Local acceptance API: http://127.0.0.1:18164/health. Local files: {preview}", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=18164, access_log=False)
    finally:
        infrastructure.close()


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[2], Path(sys.argv[1]).resolve())

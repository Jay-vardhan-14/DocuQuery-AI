import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import create_user, get_auth_headers

@pytest.mark.asyncio
async def test_admin_endpoints(client: AsyncClient, db_session: AsyncSession):
    # Create admin user
    admin = await create_user(db_session, email="admin2@test.com", role="admin")
    headers = get_auth_headers(admin)
    
    # Get users
    res = await client.get("/api/v1/admin/users", headers=headers)
    assert res.status_code == 200
    
    # Get metrics
    res = await client.get("/api/v1/admin/metrics", headers=headers)
    assert res.status_code == 200
    
    # Get audit logs
    res = await client.get("/api/v1/admin/audit-logs", headers=headers)
    assert res.status_code == 200

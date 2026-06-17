import asyncio

import httpx

from app.core.config import settings


async def test():
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            "https://api.clerk.com/v1/users/user_3F1fR5VmF7lY84WqGrXMZw6Gb1F/metadata",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            json={
                "public_metadata": {"tenant_id": "00000000-0000-0000-0000-000000000000"},
            }
        )
        print("Metadata Status:", resp.status_code)
        print("Metadata Response:", resp.text)

        resp2 = await client.patch(
            "https://api.clerk.com/v1/users/user_3F1fR5VmF7lY84WqGrXMZw6Gb1F",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            json={
                "first_name": "Test",
                "last_name": "Doctor"
            }
        )
        print("Profile Status:", resp2.status_code)
        print("Profile Response:", resp2.text)

asyncio.run(test())

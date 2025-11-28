import json
import logging

import httpx
from fastapi import APIRouter, HTTPException
from models import NewUser, NewPayment, UserData
from redis.asyncio import Redis as aioredis

from config import config # noqa

logger = logging.getLogger('gateway')

redis = aioredis.from_url("redis://localhost")

router = APIRouter()

@router.get("/api/users/{user_id}")
async def get_user_via_gateway(user_id: int) -> UserData:

    cached = await redis.get(f'user:{user_id}')
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient() as client:
            url = f"{config.url.db}/users/{user_id}"
            response = await client.get(
                url=url,
                timeout=5.0
            )
            await redis.hset(f'user:{user_id}', mapping=response)
            return response.json()

    except Exception as e:
        logger.error(f'Failed to redirect request: {e}')

@router.post("/api/users")
async def create_user_via_gateway(user_data: NewUser, payment_data: NewPayment):
    try:
        async with httpx.AsyncClient() as client:
            url = f"{config.url.db}/users"
            resp = await client.post(
                url=url,
                json=user_data.model_dump(),
                timeout=10.0
            )
            await redis.delete(f'user:{user_data.user_id}')
            logger.info(f"Successfully posted: {resp.status_code}")

            resp = await client.post(
                url=url,
                json=payment_data.model_dump(),
                timeout=10.0
            )
            logger.info(f"Successfully posted: {resp.status_code}")
            return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")

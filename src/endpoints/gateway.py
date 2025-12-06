import json
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.params import Query
from redis.asyncio import Redis as aioredis

from src.config import config
from src.models import NewUser, NewPayment, UserData, NewDueTo

logger = logging.getLogger('gateway')

redis = aioredis.from_url("redis://")

router = APIRouter(prefix='/api')

@router.get("/due_to")
async def get_users_due_to(user_id = Query(..., description="User ID")):
    cached = await redis.get(f'due_to:{user_id}')
    if cached:
        return json.loads(cached)

    async with httpx.AsyncClient() as client:
        url = f"{config.url.db}/due_to/{user_id}"
        response = await client.get(
            url=url,
            timeout=5.0
        )
        await redis.hset(f'due_to:{user_id}', mapping=response)
        return response.json()


@router.post("/due_to")
async def get_users_due_to(user_data: "NewDueTo"):
    try:
        async with httpx.AsyncClient() as client:
            url = f"{config.url.db}/due_to"
            resp = await client.post(
                url=url,
                json=user_data.model_dump(),
                timeout=10.0
            )
            await redis.delete(f'due_to:{user_data.user_id}')
            logger.info(f"Successfully posted: {resp.status_code}")

            resp = await client.post(
                url=url,
                json=user_data.model_dump(),
                timeout=10.0
            )
            logger.info(f"Successfully posted: {resp.status_code}")
            return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")


@router.get("/users/{user_id}")
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

@router.post("/users")
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

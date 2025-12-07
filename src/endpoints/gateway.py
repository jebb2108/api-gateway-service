import json
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.params import Query
from redis.asyncio import Redis as aioredis

from src.config import config
from src.models import User, Payment, UserData

logger = logging.getLogger('gateway')

redis = aioredis.from_url("redis://redis")

router = APIRouter(prefix='/api')

DATABASE_BASE_URL = f"http://{config.database.host}:{config.database.port}"
PAYMENT_BASE_URL = f"http://{config.payments.host}:{config.payments.port}"


@router.post("/test_connection")
async def test_connection():
    """Тест соединения с database-сервисом"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"http://{config.database.host}:{config.database.port}/health"
            logger.info(f"Testing connection to: {url}")
            response = await client.get(url, timeout=5.0)
            return {
                "status": "success",
                "database_url": url,
                "response": response.text
            }
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {
            "status": "error",
            "database_host": config.database.host,
            "database_port": config.database.port,
            "error": str(e)
        }


@router.get("/get_due_to")
async def get_users_due_to(user_id = Query(..., description="User ID")):
    cached = await redis.get(f'due_to:{user_id}')
    if cached:
        return json.loads(cached)

    async with httpx.AsyncClient() as client:
        url = PAYMENT_BASE_URL + f"{config.payments.handler.prefix}/due_to?user_id={user_id}"
        response = await client.get(
            url=url,
            timeout=5.0
        )
        data = response.json()
        until = data.get('until')
        await redis.hset(f'due_to:{user_id}', mapping=until)
        return until


@router.post("/create_payment")
async def get_users_due_to(user_data: Payment):
    try:
        async with httpx.AsyncClient() as client:
            url = PAYMENT_BASE_URL + f"{config.payments.handler.prefix}/add"
            resp = await client.post(
                url=url,
                json=user_data.model_dump(),
                timeout=10.0
            )
            await redis.delete(f'due_to:{user_data.user_id}')
            logger.info(f"Successfully posted: {resp.status_code}")

            return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")

@router.get("/users")
async def get_user_via_gateway(
        user_id: int = Query(..., description="User ID"),
        target_field = Query(..., description="What exactly the server looks for")
) -> UserData:

    cached = await redis.get(f'user:{user_id}')
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient() as client:
            url = DATABASE_BASE_URL + f"/users?user_id={user_id}&target_field={target_field}"
            response = await client.get(
                url=url,
                timeout=5.0
            )
            await redis.hset(f'user:{user_id}', mapping=response)
            return response.json()

    except Exception as e:
        logger.error(f'Failed to redirect request: {e}')


@router.post("/users")
async def create_user_via_gateway(user_data: User, payment_data: Payment):
    try:
        async with httpx.AsyncClient() as client:
            # 1. Создание пользователя в базе данных
            database_url = DATABASE_BASE_URL + f"{config.database.prefix}/users"
            resp = await client.post(
                url=database_url,
                json=user_data.model_dump_json(),
                timeout=10.0
            )
            await redis.delete(f'user:{user_data.user_id}')
            logger.info(f"Successfully posted to database: {resp.status_code}")

            # 2. Создание платежа в платежном сервисе
            payment_url = PAYMENT_BASE_URL + f"{config.payments.handler.prefix}/add"
            resp = await client.post(
                url=payment_url,
                json=payment_data.model_dump_json(),
                timeout=10.0
            )
            logger.info(f"Successfully posted to payment service: {resp.status_code}")

            return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")

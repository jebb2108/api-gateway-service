import json
import logging
from json import loads
from typing import Any, Union

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.params import Query
from redis.asyncio import Redis as aioredis

from src.config import config
from src.models import User, Payment, Profile

logger = logging.getLogger('gateway')

redis = aioredis.from_url("redis://redis")

router = APIRouter(prefix='/api')

DATABASE_BASE_URL = f"http://{config.database.host}:{config.database.port}"
PAYMENT_BASE_URL = f"http://{config.payments.host}:{config.payments.port}"


@router.get("/test_connection")
async def test_connection():
    """Тест соединения с database-сервисом"""
    try:
        async with (httpx.AsyncClient() as client):
            url = f"http://{config.database.host}:{config.database.port}" + \
                  f"{config.database.prefix}/health"

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


@router.get("/due_to")
async def get_users_due_to(user_id = Query(..., description="User ID")):

    cached = await redis.hgetall(f'due_to:{user_id}')
    if cached:
        return { key: loads(val) for key, val in cached.items() }

    async with httpx.AsyncClient() as client:
        url = PAYMENT_BASE_URL + f"{config.payments.handler.prefix}/due_to?user_id={user_id}"
        try:
            response = await client.get(
                url=url,
                timeout=5.0
            )
            if response.status_code == 200:
                if data := response.json():
                    mapping = {key: json.dumps(value) for key, value in data.items()}
                    await redis.hset(f'due_to:{user_id}', mapping=mapping)

                return data # Возвращает либо словарь, либо null

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")

@router.get('/yookassa_link')
async def get_yookassa_link(
        user_id: int = Query(..., description="User ID")
) -> str:
    async with httpx.AsyncClient() as client:
        url = PAYMENT_BASE_URL + config.payments.handler.prefix + f'/link?user_id={user_id}'
        try:
            response = await client.get(url, timeout=5.0)
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to receive link: {e}")

@router.post("/create_payment")
async def get_users_due_to(user_data: Payment):
    try:
        async with httpx.AsyncClient() as client:
            url = PAYMENT_BASE_URL + config.payments.handler.prefix + "/add"
            response = await client.post(
                url=url,
                json=user_data.model_dump(),
                timeout=10.0
            )
            await redis.delete(f'due_to:{user_data.user_id}')
            if response.status_code == 200:
                logger.info(f"Successfully posted: {response.status_code}")
                return {"status": "success"}

            return {"status": "failed", "error": response.status_code, "response": response.text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")

@router.get("/nicknames")
async def check_nickname_exists(
        nickname: str = Query(..., description="Some user`s nickname")
) -> bool:
    async with httpx.AsyncClient() as client:
        url = DATABASE_BASE_URL + config.database.prefix + \
              f'/nickname_exists?nickname={nickname}'
        response = await client.get(url=url, timeout=5.0)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error connecting to server")


@router.get("/users")
async def get_user_via_gateway(
        user_id: int = Query(..., description="User ID"),
        target_field = Query(None, description="What exactly the server looks for")
) -> dict[str, int] | Any:

    if target_field is None:
        async with (httpx.AsyncClient() as client):
            url = DATABASE_BASE_URL + config.database.prefix + \
                f'/user_exists?user_id={user_id}'
            response = await client.get(url=url, timeout=5.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=500, detail="Error connecting to server")

    cached = await redis.hgetall(f'user:{user_id}:{target_field}')
    if cached:
        return {key: loads(val) for key, val in cached.items()}

    try:
        async with httpx.AsyncClient() as client:
            url = DATABASE_BASE_URL + config.database.prefix + \
                  f"/users?user_id={user_id}&target_field={target_field}"
            response = await client.get(
                url=url,
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                mapping = {key: json.dumps(value) for key, value in data.items()}
                await redis.hset(f'user:{user_id}:{target_field}', mapping=mapping)
                return response

            elif response.status_code == 405:
                return None

            return {"status": "failed", "error": response.status_code, "response": response.text}

    except Exception as e:
        logger.error(f'Failed to redirect request: {e}')


@router.post("/users")
async def create_user_via_gateway(user_data: User):
    try:
        async with httpx.AsyncClient() as client:
            # 1. Создание пользователя в базе данных
            database_url = DATABASE_BASE_URL + f"{config.database.prefix}/users"
            headers = {"Content-Type": "application/json"}
            resp = await client.post(
                url=database_url,
                headers=headers,
                content=user_data.model_dump_json(),
                timeout=10.0
            )
            await redis.delete(f'user:{user_data.user_id}')
            logger.info(f"Successfully posted to database: {resp.status_code}")

            # 2. Создание платежа в платежном сервисе
            payment_url = PAYMENT_BASE_URL + f"{config.payments.handler.prefix}/add"
            default_payment = Payment(user_id=user_data.user_id)
            resp = await client.post(
                url=payment_url,
                headers=headers,
                content=default_payment.model_dump_json(),
                timeout=10.0
            )
            logger.info(f"Successfully posted to payment service: {resp.status_code}")

            return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update DB: {e}")

@router.put('/update_profile')
async def update_user_profile(
        updated_data: Union[User, Profile]
):
    """ Обновляет информацию о пользователе """
    try:
        if isinstance(updated_data, User):
            async with httpx.AsyncClient() as client:
                database_url = DATABASE_BASE_URL + f"{config.database.prefix}/users"
                headers = {"Content-Type": "application/json"}
                resp = await client.post(
                    url=database_url,
                    headers=headers,
                    json=updated_data.model_dump(),
                    timeout=10.0
                )
                logger.info(f"Successfully updated user: {resp.status_code}")
                await redis.delete(f'user:{updated_data.user_id}:users')
        else:
            async with httpx.AsyncClient() as client:
                database_url = DATABASE_BASE_URL + f"{config.database.prefix}/profiles"
                headers = {"Content-Type": "application/json"}
                resp = await client.post(
                    url=database_url,
                    headers=headers,
                    json=updated_data.model_dump(),
                    timeout=10.0
                )
                logger.info(f"Successfully updated profile: {resp.status_code}")
                await redis.delete(f'user:{updated_data.user_id}:profiles')

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating data: {e}")

import uvicorn
from fastapi import FastAPI

from src.config import config
from src.endpoints.gateway import router

app = FastAPI()
app.include_router(router)


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=config.payments.host,
        port=config.payments.port
    )

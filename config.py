import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv('.env')

@dataclass(frozen=True)
class UrlConfig:
    db: str = os.getenv('DB_URL')

@dataclass
class Config:

    url = None

    def __post_init__(self):
        if not self.url: self.url = UrlConfig()


config = Config()
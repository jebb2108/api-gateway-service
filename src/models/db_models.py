from enum import Enum
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel

class Language(str, Enum):
    """
    Поддерживаемые языки
    """
    RU = "ru"
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"


class Topic(str, Enum):
    """
    Темы для общения
    """
    GENERAL = "general"
    MUSIC = "music"
    MOVIES = "movies"
    SPORTS = "sports"
    TECHNOLOGY = "technology"
    TRAVEL = "travel"
    GAMES = "games"


class NewUser(BaseModel):
    """
    Модель нового пользователя (для базы данных).
    """
    user_id: int
    username: Optional[str]
    camefrom: str
    first_name: str
    language: str
    fluency: int
    topics: List[str]
    lang_code: str


class NewDueTo(BaseModel):
    user_id: int
    due_to: datetime


class UserData(BaseModel):
    """
    Модель зарегистрированного пользователя (в базе данных).
    """
    user_id: int
    username: Optional[str]
    camefrom: str
    first_name: str
    language: str
    fluency: int
    topics: List[str]
    lang_code: str
    nickname: Optional[str]
    age: Optional[int]
    about: Optional[str]
    status: Optional[str]


class NewPayment(BaseModel):
    user_id: int
    currency: Optional[str] = 'RUB'
    trial: Optional[bool] = True
    period: Optional[str] = 'month'
    until: datetime



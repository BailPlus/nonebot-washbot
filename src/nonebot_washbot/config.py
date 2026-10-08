from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    WASHBOT_TARGET_GROUP_ID: int
    WASH_MACHINE_URL: str
    WASHBOT_USER_WHITELIST: list[str] = []


config = get_plugin_config(Config)

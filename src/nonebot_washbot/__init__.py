import traceback
from datetime import datetime, timedelta

from httpx import URL, AsyncClient, RequestError
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText, CommandArg
from nonebot.plugin import PluginMetadata

from nonebot_washbot.config import Config, config

__plugin_meta__ = PluginMetadata(
    name="nonebot-washbot",
    description="洗衣机器人，远程操控寝室洗衣机",
    usage="",
    config=Config,
)
VALID_LEVELS = {"1": 7, "3": 0, "4": 0, "4p": 41, "6": 60}  # {洗衣模式: 所需分钟}

wash_cmd = on_command("wash")
client = AsyncClient()
wash_after = datetime.now()  # 在此时间后才可以洗衣服


@wash_cmd.handle()
async def _(matcher: Matcher, event: GroupMessageEvent, arg: Message = CommandArg()):
    if event.group_id != config.WASHBOT_TARGET_GROUP_ID:
        await matcher.finish()
    argstr = arg.extract_plain_text().strip()
    if not argstr:
        return
    matcher.set_arg("level", arg)


@wash_cmd.got("level", prompt=f"请输入洗衣等级{list(VALID_LEVELS)}")
async def _(matcher: Matcher, event: GroupMessageEvent, level: str = ArgPlainText()):
    global wash_after
    if event.group_id != config.WASHBOT_TARGET_GROUP_ID:
        await matcher.finish()

    if level.startswith("/wash "):
        level = level[6:]
    level = level.strip()
    if not level:
        await wash_cmd.reject(f"请输入洗衣等级{list(VALID_LEVELS)}")
    elif level not in VALID_LEVELS:
        await wash_cmd.finish(
            f"无效的洗衣等级。可选项：{list(VALID_LEVELS)}。请重新输入命令"
        )

    now = datetime.now()
    if now < wash_after:
        await wash_cmd.finish(
            f"洗衣机正在工作中。请于{int((wash_after - now).total_seconds() // 60) or '不足1'}分钟后重试"
        )

    try:
        resp = await client.post(
            URL(config.WASH_MACHINE_URL).copy_with(path="/" + level)
        )
    except RequestError as e:
        traceback.print_exc()
        await matcher.finish(f"执行失败：与洗衣机的连接可能已断开\n{repr(e)}")
    if resp.status_code != 200:
        await matcher.finish(f"执行失败：错误的状态码：{resp.status_code}")

    wash_need_minutes = VALID_LEVELS[level]
    wash_after = now + timedelta(minutes=wash_need_minutes)
    await matcher.finish(f"执行成功，预计需要{wash_need_minutes}分钟")

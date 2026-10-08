import nonebot

nonebot.plugin.require("nonebot_plugin_apscheduler")

import traceback
from datetime import datetime, timedelta

from httpx import URL, AsyncClient, RequestError
from nonebot import get_bot, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText, CommandArg
from nonebot.plugin import PluginMetadata
from nonebot_plugin_apscheduler import scheduler

from nonebot_washbot.config import Config, config

__plugin_meta__ = PluginMetadata(
    name="nonebot-washbot",
    description="洗衣机器人，远程操控寝室洗衣机",
    usage="",
    config=Config,
)
VALID_LEVELS = {"1": 7, "3": 20, "4p": 41, "6": 60}  # {洗衣模式: 所需分钟}

wash_cmd = on_command("wash")
client = AsyncClient()
wash_after = datetime.now().astimezone()  # 在此时间后才可以洗衣服


@wash_cmd.handle()
async def _(matcher: Matcher, event: GroupMessageEvent, arg: Message = CommandArg()):  # noqa: B008
    if event.group_id != config.WASHBOT_TARGET_GROUP_ID:
        await matcher.finish()
    if (
        config.WASHBOT_USER_WHITELIST
        and event.get_user_id() not in config.WASHBOT_USER_WHITELIST
    ):
        await matcher.finish("Permission denied")
    argstr = arg.extract_plain_text().strip()
    if not argstr:
        return
    matcher.set_arg("level", arg)


@wash_cmd.got("level", prompt=f"请输入洗衣等级{list(VALID_LEVELS)}")
async def _(matcher: Matcher, event: GroupMessageEvent, level: str = ArgPlainText()):
    global wash_after
    if event.group_id != config.WASHBOT_TARGET_GROUP_ID:
        await matcher.finish()

    level = level.removeprefix("/wash ").strip()
    if not level:
        await wash_cmd.reject(f"请输入洗衣等级{list(VALID_LEVELS)}")
    elif level not in VALID_LEVELS:
        await wash_cmd.finish(
            f"无效的洗衣等级。可选项：{list(VALID_LEVELS)}。请重新输入命令"
        )

    now = datetime.now().astimezone()
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
        await matcher.finish(f"执行失败：与洗衣机的连接可能已断开\n{e!r}")
    if resp.status_code != 200:
        await matcher.finish(f"执行失败：错误的状态码：{resp.status_code}")

    wash_need_minutes = VALID_LEVELS[level]
    wash_after = now + timedelta(minutes=wash_need_minutes)
    await matcher.send(f"执行成功，预计需要{wash_need_minutes}分钟")
    scheduler.add_job(
        _push_wash_complete_msg,
        args=(str(event.self_id), event.group_id, event.user_id),
        next_run_time=wash_after,
        id="push",
        replace_existing=True,
        misfire_grace_time=None,
    )


async def _push_wash_complete_msg(self_id: str, gid: int, uid: int):
    bot = get_bot(self_id)
    assert isinstance(bot, Bot)
    await bot.send_group_msg(
        group_id=gid, message=MessageSegment.at(uid) + " 衣服洗好了！"
    )

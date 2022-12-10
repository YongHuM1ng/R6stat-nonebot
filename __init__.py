import asyncio
import base64
import os
import time
from dataclasses import asdict

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Bot
from nonebot.params import CommandArg, Command
# import requests
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name='R6S战绩查询',
    description='查询R6S战绩，并可生成图片',
    usage='''发送"r6 育碧ID"可查询文字战绩
发送"R6 育碧ID"可生成战绩图
不输入ID默认为群名片ID''',
    extra={'version': '1.0.0'}
)

matcher = on_command('r6', aliases={'R6'})

file_path = f'{os.path.dirname(__file__)}/'
font_bold = f'{file_path}ScoutCond-BoldItalic.otf'
font_regular = f'{file_path}ScoutCond-RegularItalic.otf'
mmr_level = {'COPPER ': '紫铜', 'BRONZE ': '青铜', 'SILVER ': '白银', 'GOLD ': '黄金', 'PLATINUM ': '白金',
             'DIAMOND ': '钻石', 'CHAMPIONS ': '冠军'}


@matcher.handle()
async def r6(ev: GroupMessageEvent, bot: Bot, cmd: tuple = Command(), args: Message = CommandArg()):
    if args.get('at'):
        qid = asdict(args.get('at')[0])['data']['qq']
        name = (await bot.get_group_member_info(group_id=ev.group_id, user_id=qid))['card']
    elif args.extract_plain_text():
        name = args.extract_plain_text()
    else:
        name = ev.sender.card

    # 同步获取
    # try:
    #     r = requests.get('https://r6.tracker.network/api/v0/overwolf/player', params={'name': name}, timeout=10)
    # except requests.exceptions.ReadTimeout:
    #     await matcher.finish('连接R6Tracker服务器超时')
    #     return
    # else:
    #     r.encoding = 'utf-8'
    #     data = r.json()

    # 异步获取
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://r6.tracker.network/api/v0/overwolf/player',
                                   params={'name': name}, timeout=10) as resp:
                data = await resp.json()
    except asyncio.exceptions.TimeoutError:
        await matcher.finish('连接R6Tracker服务器超时')

    if not data['success']:
        if data['reason'] == 'InvalidName':
            await matcher.finish('没有这个游戏ID', at_sender=True)
            return
        await matcher.finish(f"出现错误，错误原因：{data['reason']}", at_sender=True)

    if cmd == ('r6',):
        season = None
        for i in range(len(data['seasons'])):
            if data['seasons'][i]['season'] == data['currentSeason'] and data['seasons'][i]['regionLabel'] == 'CASUAL':
                season = data['seasons'][i]

        if not season:
            await matcher.finish('赛季信息获取失败')

        for i in mmr_level:
            season['rankName'] = season['rankName'].replace(i, mmr_level[i])
        await matcher.finish(
            MessageSegment.image(data["avatar"]) + '\n'
                                                   f'{data["name"]}  等级:{data["level"]}\n'
                                                   f'KD:{season["kd"]:.2f}         胜率:{season["winPct"]:.0f}%\n'
                                                   f'休闲分:{season["mmr"]}  {season["rankName"]}\n'
                                                   f'详细信息:https://r6.tracker.network/profile/pc/{data["name"]}/\n')
    elif cmd == ('R6',):
        season1, season2 = None, None
        for i in range(len(data['seasons'])):
            if data['seasons'][i]['season'] == data['currentSeason']:
                if data['seasons'][i]['regionLabel'] == 'CASUAL':
                    season1 = data['seasons'][i]
                if data['seasons'][i]['regionLabel'] == 'RANKED':
                    season2 = data['seasons'][i]

        if not (season1 and season2):
            await matcher.finish('赛季信息获取失败')

        # 优先使用远程头像
        # try:
        #     avatar = Image.open(BytesIO(requests.get(data['avatar'], timeout=10).content)).resize((150, 150))
        # except requests.exceptions.ReadTimeout:
        #     if os.path.exists(f'{file_path}cache/{data["name"]}.png'):
        #         avatar = Image.open(f'{file_path}cache/{data["name"]}.png')
        #     else:
        #         avatar = Image.open(f'{file_path}default_avatar.png')
        # else:
        #     avatar.save(f'{file_path}cache/{data["name"]}.png')

        # 优先使用本地头像
        # if os.path.exists(f'{file_path}cache/{data["name"]}.png'):
        #     avatar = Image.open(f'{file_path}cache/{data["name"]}.png')
        # else:
        #     try:
        #         avatar = Image.open(BytesIO(requests.get(data['avatar'], timeout=10).content)).resize((150, 150))
        #     except requests.exceptions.ReadTimeout:
        #         avatar = Image.open(f'{file_path}default_avatar.png')
        #     else:
        #         avatar.save(f'{file_path}cache/{data["name"]}.png')

        # 异步优先使用本地头像
        if os.path.exists(f'{file_path}cache/{data["name"]}.png'):
            avatar = Image.open(f'{file_path}cache/{data["name"]}.png')
        else:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(data['avatar'], timeout=10) as resp:
                        avatar = Image.open(BytesIO(await resp.read())).resize((150, 150))
            except asyncio.exceptions.TimeoutError:
                avatar = Image.open(f'{file_path}default_avatar.png')
            else:
                avatar.save(f'{file_path}cache/{data["name"]}.png')

        # 获取段位图
        if os.path.exists(f'{file_path}cache/{season1["rankName"]}.png'):
            casual_img = Image.open(f'{file_path}cache/{season1["rankName"]}.png').convert('RGBA')
        else:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(season1['img'], timeout=10) as resp:
                        casual_img = Image.open(BytesIO(await resp.read())).convert('RGBA')
            except asyncio.exceptions.TimeoutError:
                casual_img = Image.new('RGBA', (0, 0))
            else:
                casual_img.save(f'{file_path}cache/{season1["rankName"]}.png')

        # 获取段位图
        if os.path.exists(f'{file_path}cache/{season2["rankName"]}.png'):
            rank_img = Image.open(f'{file_path}cache/{season2["rankName"]}.png').convert('RGBA')
        else:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(season2['img'], timeout=10) as resp:
                        rank_img = Image.open(BytesIO(await resp.read())).convert('RGBA')
            except asyncio.exceptions.TimeoutError:
                rank_img = Image.new('RGBA', (0, 0))
            else:
                rank_img.save(f'{file_path}cache/{season2["rankName"]}.png')

        # casual_img = Image.open(BytesIO(requests.get(season1['img'], timeout=10).content))
        # rank_img = Image.open(BytesIO(requests.get(season2['img'], timeout=10).content)).convert('RGBA')

        back = Image.open(f'{file_path}back.png')
        draw = ImageDraw.Draw(back)

        draw.text((515, 105), f'SEASON{data["currentSeason"]}', fill="#FFFFFF",
                  font=ImageFont.truetype(font_bold, size=24))
        back.paste(avatar, (78, 184), mask=avatar)
        draw.text((256, 192), f'LEVEL {data["level"]}', fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=36))
        draw.text((256, 230), data['name'], fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=96))

        back.paste(casual_img, (125, 412), mask=casual_img)
        draw.text((181 - ImageFont.truetype(font_bold, size=16).getsize(season1['rankName'])[0] / 2, 518),
                  season1['rankName'], fill="#FFFFFF", font=ImageFont.truetype(font_bold, size=16))
        draw.text((181 - ImageFont.truetype(font_bold, size=48).getsize(str(season1['mmr']))[0] / 2, 530),
                  str(season1['mmr']), fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        draw.text((262, 446), str(round(season1['kd'], 2)), fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=48))
        draw.text((384, 446), str(season1['kills']), fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))
        draw.text((491, 446),
                  str(round(season1['kills'] / season1['kd'])) if season1['kd'] != 0 else '0',
                  fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        draw.text((262, 521), str(season1['winPct']), fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=48))
        draw.text((384, 521), str(season1['wins']), fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        if season1['winPct'] != 0:
            draw.text((491, 521), str(round(season1['wins'] / (season1['winPct'] / 100) - season1['wins'])),
                      fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))
        else:
            draw.text((491, 521), '0',
                      fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        back.paste(rank_img, (125, 676), mask=rank_img)
        draw.text((181 - ImageFont.truetype(font_bold, size=16).getsize(season2['rankName'])[0] / 2, 782),
                  season2['rankName'], fill="#FFFFFF", font=ImageFont.truetype(font_bold, size=16))
        draw.text((181 - ImageFont.truetype(font_bold, size=48).getsize(str(season2['mmr']))[0] / 2, 794),
                  str(season2['mmr']), fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        draw.text((262, 674), str(round(season2['kd'], 2)), fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=48))
        draw.text((384, 674), str(season2['kills']), fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))
        draw.text((491, 674),
                  str(round(season2['kills'] / season2['kd'])) if season2['kd'] != 0 else '0',
                  fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        draw.text((262, 749), str(season2['winPct']), fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=48))
        draw.text((384, 749), str(season2['wins']), fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        if season2['winPct'] != 0:
            draw.text((491, 749), str(round(season2['wins'] / (season2['winPct'] / 100) - season2['wins'])),
                      fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))
        else:
            draw.text((491, 749), '0',
                      fill="#FFFFFF", font=ImageFont.truetype(font_regular, size=48))

        draw.text((262, 824), season2['maxRank']['rankName'], fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=48))
        draw.text((491, 824), str(season2['maxRank']['mmr']), fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=48))

        draw.text((629, 925), time.strftime("%Y-%m-%d %H:%M", time.localtime()), fill="#FFFFFF",
                  font=ImageFont.truetype(font_regular, size=24))
        bio = BytesIO()
        back.save(bio, format='PNG')
        await matcher.finish(MessageSegment.image(f'base64://{base64.b64encode(bio.getvalue()).decode()}'))

import asyncio
import datetime
import json
import os
import pprint
import traceback
from typing import Union

import aiohttp
import discord
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

version = "2.6.1"

BLOCK_OTHER_USERS_TRACK = os.environ.get("BLOCK_OTHER_USERS_TRACK")
RPC_TOKEN = os.environ.get("RPC_TOKEN", "")

async def index(request):
    return web.Response(text="Hello!")

app = web.Application()
app.add_routes([web.get('/', index)])

def time_format(milliseconds: Union[int, float]) -> str:
    minutes, seconds = divmod(int(milliseconds / 1000), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    strings = f"{minutes:02d}:{seconds:02d}"

    if hours:
        strings = f"{hours}:{strings}"

    if days:
        strings = (f"{days} dias" if days > 1 else f"{days} dia") + (f", {strings}" if strings != "00:00" else "")

    return strings


class Assets:
    pause = "https://i.ibb.co/mDBMnH8/pause.png"
    loop = "https://i.ibb.co/5Mj4HjT/loop-track.gif"
    loop_queue = "https://i.ibb.co/5Mj4HjT/loop-track.gif"
    stream = "https://i.ibb.co/Qf9BSQb/stream.png"
    idle = "https://i.ibb.co/6XS6qLy/music-img.png"
    source = {
        "deezer": "https://i.ibb.co/zxpBbp8/deezer.png",
        "soundcloud": "https://i.ibb.co/CV6NB6w/soundcloud.png",
        "spotify": "https://i.ibb.co/3SWMXj8/spotify.png",
        "youtube": "https://i.ibb.co/LvX7dQL/yt.png",
        "twitch": "https://cdn3.iconfinder.com/data/icons/popular-services-brands-vol-2/512/twitch-512.png"
    }


class RPCActivity(discord.Activity):
    __slots__ = (
        'state', 'details', 'timestamps', 'assets', 'party', 'flags', 'sync_id', 'session_id', 'type', 'name', 'url',
        'application_id', 'emoji', 'buttons', 'metadata',
    )

    def __init__(self, **kwargs):
        self.metadata = kwargs.get("metadata")
        super().__init__(**kwargs)


class MyClient(discord.Client):
    ws_task = None
    assets = Assets()
    last_large_image = ""
    last_small_image = ""

    async def on_ready(self):
        print(f'Logado como: {self.user} [{self.user.id}]')

        await self.connect_vc()

        if not self.ws_task:
            self.ws_task = self.loop.create_task(web._run_app(app, host="0.0.0.0", port=os.environ.get("PORT", 80)))
            await self.connect_rpc_ws()

    async def connect_vc(self):

        try:
            vc = self.get_channel(int(os.environ["AUTO_CHANNEL_CONNECT_ID"]))
        except KeyError:
            return

        if not vc:
            print(f"Canal de voz não encontrado: {os.environ['AUTO_CHANNEL_CONNECT_ID']}")
            return

        if vc.guild.me.voice:
            return

        if not vc.permissions_for(vc.guild.me).connect:
            print(f"Sem permissão para conectar no canal: {vc.name}")
            return

        await vc.connect()

    async def connect_rpc_ws(self):

        backoff = 7

        while True:

            try:
                async with aiohttp.ClientSession().ws_connect(os.environ["RPC_URL"], heartbeat=30, timeout=120) as ws:

                    print(f"Websocket conectado: {os.environ['RPC_URL']}")

                    await self.wait_until_ready()

                    await ws.send_str(

                        json.dumps(
                            {
                                "op": "rpc_update",
                                "user_ids": [self.user.id],
                                "token": RPC_TOKEN,
                                "version": version
                            }
                        )
                    )

                    async for msg in ws:

                        try:

                            if msg.type == aiohttp.WSMsgType.TEXT:

                                try:
                                    data = json.loads(msg.data)
                                except Exception:
                                    print(traceback.format_exc())
                                    continue

                                try:
                                    if not data['op']:
                                        print(data)
                                        continue
                                except:
                                    print(traceback.format_exc())
                                    continue

                                bot_id = data.pop("bot_id", None)

                                bot_name = data.get("bot_name", "")

                                if data['op'] == "disconnect":
                                    print(f"op: {data['op']} | {os.environ['RPC_URL']} | reason: {data.get('reason')}")
                                    self.closing = True
                                    await ws.close()
                                    return

                                user_ws = data.pop("user", None)

                                if user_ws != self.user.id:
                                    return

                                if data['op'] == "exception":
                                    print(f"op: {data['op']} | "
                                          f"bot: {(bot_name + ' ') if bot_name else ''}[{bot_id}] | "
                                          f"\nerror: {data.get('message')}")
                                    continue

                                print(f"op: {data['op']} | bot: {(bot_name + ' ') if bot_name else ''}[{bot_id}]")

                                try:
                                    del data["token"]
                                except KeyError:
                                    pass

                                await self.process_data(user_ws, bot_id, data)

                            elif msg.type in (aiohttp.WSMsgType.CLOSED,
                                              aiohttp.WSMsgType.CLOSING,
                                              aiohttp.WSMsgType.CLOSE):

                                print(f"Conexão finalizada com o servidor: {os.environ['RPC_URL']}")
                                return

                            elif msg.type == aiohttp.WSMsgType.ERROR:

                                await self.change_presence(activity=None)

                                if self.closing:
                                    return

                                print(
                                    f"Conexão perdida com o servidor: {os.environ['RPC_URL']} | Reconectando em {time_format(backoff)} seg. {repr(ws.exception())}")

                                await asyncio.sleep(backoff)
                                backoff *= 1.3

                            else:
                                print(f"Unknow message type: {msg.type}")

                        except:
                            print(traceback.format_exc())

                    print(
                        f"Desconectado: {os.environ['RPC_URL']} | Nova tentativa de conexão em "
                        f"{time_format(7 * 1000)}..."
                    )
                    await self.change_presence(activity=None)
                    await asyncio.sleep(7)

            except (aiohttp.WSServerHandshakeError, aiohttp.ClientConnectorError) as e:

                tm = backoff * 5

                print(
                    f"Servidor indisponível: {os.environ['RPC_URL']} | Nova tentativa de conexão em {time_format(tm * 1000)}.")
                await asyncio.sleep(tm)
                backoff *= 2

            except Exception:
                print(traceback.format_exc())

    async def process_data(self, user_id: int, bot_id: int, data: dict):

        data = dict(data)

        if data['op'] == "update":
            try:
                await self.update(user_id, bot_id, data)
            except:
                print(traceback.format_exc())

        elif data['op'] == "idle":
            payload = self.get_idle_data(bot_id, data)
            await self.update(user_id, bot_id, payload)

        elif data['op'] == "close":
            await self.change_presence(activity=None)

        else:
            print(f"unknow op: {data}")

    async def update(self, user_id: int, bot_id: int, data: dict):

        data = dict(data)

        if not data:
            await self.change_presence(activity=None)
            return

        payload = {
            "name": "#".join(data["bot_name"].split("#")[:-1]),
            "type": discord.ActivityType.playing,
            "timestamps": {},
            "assets": {
                "small_image": "https://i.ibb.co/qD5gvKR/cd.gif"
            },
        }

        buttons = []

        track = data.pop("track", None)
        thumb = data.pop("thumb", None)

        payload.update(data)

        if not payload["assets"].get("large_image"):
            payload["assets"]["large_image"] = thumb

        if track:

            if track["thumb"]:
                payload["assets"]["large_image"] = track["thumb"].replace("mqdefault", "default")

            payload['details'] = track["title"]

            if track["stream"]:

                if track["source"] == "twitch":
                    payload['assets']['small_image'] = self.assets.source[track["source"]]
                    payload['assets']['small_text'] = "Twitch: Ao vivo"
                else:
                    payload['assets']['small_image'] = self.assets.stream
                    payload['assets']['small_text'] = "Ao vivo"

            if not track["paused"]:

                if not track["stream"]:
                    startTime = discord.utils.utcnow()
                    endtime = (discord.utils.utcnow() + datetime.timedelta(
                        milliseconds=track["duration"] - track["position"]))

                    payload['timestamps'] = {
                        'start': int(startTime.timestamp()),
                        'end': int(endtime.timestamp())
                    }

                    player_loop = track.get('loop')

                    if player_loop:

                        if player_loop == "queue":
                            loop_text = "Repetição: Fila"
                            payload['assets']['small_image'] = self.assets.loop_queue

                        else:

                            if isinstance(player_loop, list):
                                loop_text = f"Repetição da fila: ativada: {player_loop[0]}/{player_loop[1]}."
                            elif isinstance(player_loop, int):
                                loop_text = f"Repetições restantes: {player_loop}"
                            else:
                                loop_text = "Repetição ativada"

                            payload['assets']['small_image'] = self.assets.loop

                        payload['assets']['small_text'] = loop_text

                    else:
                        try:
                            payload['assets']['small_image'] = self.assets.source[track["source"]]
                        except KeyError:
                            pass
                        payload['assets']['small_text'] = track["source"]

                else:
                    payload['timestamps']['start'] = int(discord.utils.utcnow().timestamp())

            else:

                payload['assets']['small_image'] = self.assets.pause
                payload['assets']['small_text'] = "em pausa"

            state = ""

            if (url := track.get("url")):
                buttons.append({"label": "Ouvir esta música", "url": url.replace("www.", "")})

            state += f'Por: {track["author"]}'

            playlist_url = track.get("playlist_url")
            playlist_name = track.get("playlist_name")
            album_url = track.get("album_url")
            album_name = track.get("album_name")

            if playlist_name and playlist_url:

                if (playlist_size := len(playlist_name)) > 25:
                    state += f' | Playlist: {playlist_name}'
                    buttons.append(
                        {"label": "Ver Playlist", "url": playlist_url.replace("www.", "")})

                else:

                    if playlist_size < 15:
                        playlist_name = f"Playlist: {playlist_name}"

                    buttons.append({"label": playlist_name, "url": playlist_url.replace("www.", "")})

            elif state and playlist_name:
                state += f' | {playlist_name}'

            elif playlist_name:
                state += f'Playlist: {playlist_name}'

            if album_url:

                if len(buttons) < 2:

                    if (album_size := len(album_name)) > 22:
                        state += f' | Álbum: {album_name}'
                        buttons.append({"label": "Ver álbum", "url": album_url.replace("www.", "")})

                    else:

                        if album_size < 17:
                            album_name = f"Álbum: {album_name}"

                        buttons.append({"label": album_name, "url": album_url})

                elif album_name != track["title"]:
                    state += f' | álbum: {album_name}'

            try:
                if track["247"]:
                    state += " | ✅24/7"
            except KeyError:
                pass

            try:
                if track["queue"]:
                    state += f' | Músicas na fila: {track["queue"]}'
            except KeyError:
                pass

            if not state:
                state = "   "

            payload['state'] = state

        external_assets = []

        payload["assets"].update({
            "large_image": payload["assets"]["large_image"].replace(
                "https://media.discordapp.net/", "mp:attachments/"
            ).replace(
                "https://cdn.discordapp.com/", "mp:attachments/"
            ),
            "small_image": payload["assets"]["small_image"].replace(
                "https://media.discordapp.net/", "mp:attachments/"
            ).replace(
                "https://cdn.discordapp.com/", "mp:attachments/"
            ),
        })

        if not payload["assets"]["large_image"].startswith("mp:attachments/") and payload["assets"][
            "large_image"] != self.last_large_image:
            external_assets.append(payload["assets"]["large_image"])

        if not payload["assets"]["small_image"].startswith("mp:attachments/") and payload["assets"][
            "small_image"] != self.last_small_image:
            external_assets.append(payload["assets"]["small_image"])

        if external_assets:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f'https://discord.com/api/v9/applications/{bot_id}/external-assets',
                        headers={
                            'Authorization': os.environ["TOKEN"],
                            'Content-Type': 'application/json'
                        }, data=json.dumps(
                            {
                                'urls': external_assets
                            }
                        )) as r:
                    resp = await r.json()

                for d in resp:
                    if d['url'] == payload["assets"]["large_image"]:
                        self.last_large_image = f'mp:{d["external_asset_path"]}'
                        payload["assets"]["large_image"] = self.last_large_image
                    elif d['url'] == payload["assets"]["small_image"]:
                        self.last_small_image = f'mp:{d["external_asset_path"]}'
                        payload["assets"]["small_image"] = self.last_small_image

        else:
            self.last_large_image = payload["assets"]["large_image"]
            self.last_small_image = payload["assets"]["small_image"]

        button_labels = []
        button_urls = []

        for b in buttons:
            button_labels.append(b["label"])
            button_urls.append(b["url"])

        if button_urls:
            payload["buttons"] = button_labels
            payload["metadata"] = {"button_urls": button_urls}

        activity = RPCActivity(application_id=str(bot_id), **payload)

        try:

            if BLOCK_OTHER_USERS_TRACK == "true" and track and track["requester_id"] != user_id:
                await self.change_presence(activity=None)
            else:
                await self.change_presence(activity=activity)

        except Exception:
            print(traceback.format_exc())
            pprint.pprint(payload)

    def get_idle_data(self, bot_id: int, data: dict):

        data = dict(data)

        payload = {
            "thumb": data.pop("thumb", None),
            "assets": {},
            "details": "Aguardando por",
            "state": "novas músicas..."
        }

        try:
            payload["timestamps"] = {"end": data["idle_endtime"]}
        except KeyError:
            pass

        buttons = []

        public = data.pop("public", True)
        support_server = data.pop("support_server", None)

        if public:
            invite = f"https://discord.com/api/oauth2/authorize?client_id={bot_id}&" \
                     f"permissions={data.pop('invite_permissions', 8)}&scope=bot%20applications.commands"
            buttons.append({"label": "Me adicione no seu server", "url": invite})
            if support_server:
                buttons.append({"label": "Servidor de suporte", "url": support_server})

        if buttons:
            payload["buttons"] = buttons

        return payload


client = MyClient()

@client.event
async def on_voice_state_update(member, before, after):

    if member.id != client.user.id:
        return

    if after.channel:
        return

    else:
        try:
            member.guild.voice_client.cleanup()
        except:
            pass

    try:
        if member.voice or str(before.channel.id) != os.environ["AUTO_CHANNEL_CONNECT_ID"]:
            return
    except:
        return

    await client.connect_vc()

try:
    client.run(os.environ["TOKEN"])
except discord.HTTPException as e:
    if e.status == 429 or "429 Too Many Requests" in str(e):
        os.system("kill 1")
    else:
        raise e

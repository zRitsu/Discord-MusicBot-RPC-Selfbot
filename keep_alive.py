from os import environ
from threading import Thread

from aiohttp import web


async def index(request):
    return web.Response(text="Hello!")

def keep_alive():
    app = web.Application()
    app.add_routes([web.get('/', index)])
    t = Thread(target=web.run_app, args=(), kwargs={"app": app, "host": "localhost", "port": environ.get("PORT", "80")})
    t.start()

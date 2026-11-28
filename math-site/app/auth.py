"""디스코드 로그인: 지정한 디스코드 서버의 멤버만 들어올 수 있다."""
import os
import secrets
from urllib.parse import urlencode

import httpx

API = "https://discord.com/api/v10"
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")
TEACHER_IDS = {x.strip() for x in os.environ.get("TEACHER_DISCORD_IDS", "").split(",") if x.strip()}
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
DEV_LOGIN = os.environ.get("DEV_LOGIN") == "1"


def redirect_uri():
    return BASE_URL + "/auth/callback"


def authorize_url(request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return "https://discord.com/oauth2/authorize?" + urlencode({
        "client_id": CLIENT_ID, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": "identify guilds.members.read", "state": state, "prompt": "none"})


async def exchange(code):
    """코드 → (discord_id, 표시이름). 서버 멤버가 아니면 None."""
    async with httpx.AsyncClient(timeout=15) as c:
        tok = await c.post(API + "/oauth2/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()},
            auth=(CLIENT_ID, CLIENT_SECRET))
        tok.raise_for_status()
        h = {"Authorization": "Bearer " + tok.json()["access_token"]}
        me = (await c.get(API + "/users/@me", headers=h)).json()
        m = await c.get(f"{API}/users/@me/guilds/{GUILD_ID}/member", headers=h)
        if m.status_code != 200:
            return None
        member = m.json()
        name = member.get("nick") or me.get("global_name") or me.get("username") or "학생"
        return me["id"], name

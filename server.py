
from aiohttp import web
import json

from sqlalchemy.exc import IntegrityError

from models import Session, Advert, engine


app = web.Application()


async def context_orm(app: web.Application):
    await engine.begin()
    yield
    await engine.dispose()


@web.middleware
async def session_middleware(request: web.Request, handler):
    async with Session() as session:
        request["session"] = session
        response = await handler(request)
        return response


app.cleanup_ctx.append(context_orm)
app.middlewares.append(session_middleware)


def get_http_error(error_class, description: str):
    return error_class(
        text=json.dumps({"status": "error", "description": description}),
        content_type="application/json",
    )


async def get_advert(advert_id, session: Session):
    advert = await session.get(Advert, advert_id)
    if advert is None:
        raise get_http_error(web.HTTPNotFound, "Advert not found")
    return advert


async def add_advert(advert: Advert, session: Session):
    try:
        session.add(advert)
        await session.commit()
    except IntegrityError as e:
        raise get_http_error(web.HTTPConflict, "Advert already exists")
    return advert


class AdvertView(web.View):
    @property
    def session(self):
        return self.request["session"]

    @property
    def advert_id(self):
        return int(self.request.match_info["advert_id"])

    async def get(self):
        advert = await get_advert(self.advert_id, self.session)
        return web.json_response(
            {
                "id": advert.id,
                "title": advert.title,
                "creation_time": advert.creation_time.isoformat(),
            }
        )

    async def post(self):
        json_validated = await self.request.json()
        advert = Advert(**json_validated)
        advert = await add_advert(advert, self.session)
        return web.json_response(
            {
                "id": advert.id,
            }
        )

    async def patch(self):
        json_validated = await self.request.json()
        advert = await get_advert(self.advert_id, self.session)
        for field, value in json_validated.items():
            setattr(advert, field, value)
            advert = await add_advert(advert, self.session)
        return web.json_response(
            {
                "id": advert.id,
            }
        )

    async def delete(self):
        advert = await get_advert(self.advert_id, self.session)
        await self.session.delete(advert)
        await self.session.commit()
        return web.json_response(
            {
                "status": "success",
            }
        )

app.add_routes(
    [
        web.post("/advert", AdvertView),
        web.get("/advert/{advert_id:\d+}", AdvertView),
        web.patch("/advert/{advert_id:\d+}", AdvertView),
        web.delete("/advert/{advert_id:\d+}", AdvertView),
    ]
)

if __name__ == "__main__":
    web.run_app(app)
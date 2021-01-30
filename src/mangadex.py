import asyncio
import gc
import os
import sys
from dataclasses import dataclass

import httpx

# from pathlib import Path


# import uvloop

# I want to go as fast as possible for small scripts,
# and a few manual dels is primarily useful for readability
# (the memory freed is barely thorough in comparison)
gc.disable()


@dataclass
class Chapter:
    id: int
    name: str
    number: str


async def _main(*, page, workers):
    # TODO: https://www.python-httpx.org/http2/
    http = httpx.AsyncClient(base_url="https://api.mangadex.org/v2/", timeout=None)
    print("Getting chapter list.")

    # https://mangadex.org/title/499/teppu/
    manga_id = page.rstrip("/").split("/")[-2]
    # r = await http.get(f"/manga/{manga_id}")
    # r.raise_for_status()
    # data_manga = r.json()["data"]
    # title = data_manga["title"]
    # title_p = Path(title)
    # title_p.mkdir(exist_ok=True)
    # del data_manga

    lang = "gb"  # english. They don't support this as a query param.
    r = await http.get(f"/manga/{manga_id}/chapters")
    r.raise_for_status()
    data_chapters = r.json()["data"]["chapters"]
    chapters = [
        Chapter(
            id=_["id"],
            name=_["title"],
            number=_["chapter"],
        )
        for _ in data_chapters
        if _["language"] == lang
    ]
    del data_chapters

    print(f"Found {len(chapters)} chapters (lang {lang}).")

    for c in chapters:
        # TODO: make this not sequential.
        r = await http.get(f"/chapter/{c.id}")
        r.raise_for_status()
        chapter_data = r.json()["data"]

        # btw there's a serverFallback, I'm ignoring for now.
        image_uris = [
            f"{chapter_data['server']}{filename}" for filename in chapter_data["pages"]
        ]
        del chapter_data

        # TODO: populate a global client pool
        # as we queue the requests to make
        # also skip if file exists
        print("\n".join(image_uris))

        # chapter_p = title_p / c.number
        # image_p = chapter_p / page_name
        # image_p.is_file()

    await http.aclose()


def main():
    # TODO: argparse
    if len(sys.argv) < 2:
        sys.exit(f"""usage: {sys.argv[0]} PAGE [# workers]""")

    page = sys.argv[1]

    try:
        num_workers = int(sys.argv[2])
    except IndexError:
        num_workers = os.cpu_count()
        if not num_workers:
            raise RuntimeError("Couldn't determine CPU count.")

    assert num_workers > 0

    # This takes a little while to warmup.
    # uvloop.install()
    asyncio.run(_main(page=page, workers=num_workers))

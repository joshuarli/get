import asyncio
import gc
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

# import uvloop

# I want to go as fast as possible for small, short-running scripts.
gc.disable()


@dataclass
class Chapter:
    id: int
    name: str
    number: str


@dataclass
class Page:
    http_client: httpx.AsyncClient
    http_path: str
    dest: Path


async def _main(*, manga_url, workers):
    # TODO: https://www.python-httpx.org/http2/
    # API v2 documentation can be read at https://api.mangadex.org/v2/
    api = httpx.AsyncClient(base_url="https://api.mangadex.org/v2/", timeout=None)
    print("Getting chapter list.")

    # https://mangadex.org/title/499/teppu/
    manga_id = manga_url.rstrip("/").split("/")[-2]
    r = await api.get(f"/manga/{manga_id}")
    r.raise_for_status()
    data_manga = r.json()["data"]
    title = data_manga["title"]
    title_p = Path(title)

    lang = "gb"  # english. They don't support this as a query param yet.
    chapter_q = asyncio.Queue()
    r = await api.get(f"/manga/{manga_id}/chapters")
    r.raise_for_status()
    data_chapters = r.json()["data"]["chapters"]
    for c in data_chapters:
        if c["language"] == lang:
            chapter_q.put_nowait(
                Chapter(
                    id=c["id"],
                    name=c["title"],
                    number=c["chapter"],
                )
            )

    print(f"Found {chapter_q.qsize()} chapters (lang {lang}).")

    downloaders = dict()  # are dicts async safe?
    page_q = asyncio.Queue()

    # Consume from chapter_q, produce to page_q.
    async def page_worker():
        while True:
            try:
                chapter = chapter_q.get_nowait()
            except asyncio.QueueEmpty:
                return

            # TODO: add switch to pass query param saver=true for pre-compressed images
            r = await api.get(f"/chapter/{chapter.id}")
            r.raise_for_status()
            chapter_data = r.json()["data"]

            # btw there's a serverFallback, I'm ignoring for now.
            for filename in chapter_data["pages"]:
                # Build up the client pool.
                server = chapter_data["server"]
                if server not in downloaders:
                    downloaders[server] = httpx.AsyncClient(
                        base_url=server, timeout=None
                    )

                dest_p = title_p / chapter.number / filename
                print(dest_p)

                if dest_p.is_file():
                    print(f"skipped {dest_p} because file exists.")
                    continue

                p = Page(
                    http_client=downloaders[server],
                    http_path=filename,
                    dest=dest_p,
                )
                page_q.put_nowait(p)

    # TODO: download
    await asyncio.gather(*(page_worker() for _ in range(workers)))

    print(page_q.qsize())

    await api.aclose()
    for http_client in downloaders.values():
        await http_client.aclose()


def main():
    # TODO: argparse
    if len(sys.argv) < 2:
        sys.exit(f"""usage: {sys.argv[0]} PAGE [# workers]""")

    manga_url = sys.argv[1]

    try:
        num_workers = int(sys.argv[2])
    except IndexError:
        num_workers = os.cpu_count()
        if not num_workers:
            raise RuntimeError("Couldn't determine CPU count.")

    assert num_workers > 0

    # This takes a little while to warmup.
    # uvloop.install()
    asyncio.run(_main(manga_url=manga_url, workers=num_workers))

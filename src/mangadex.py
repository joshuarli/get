import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
import uvloop


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

    async def download(self):
        print(self.dest)
        r = await self.http_client.get(self.http_path)
        r.raise_for_status()
        # TODO: We could avoid a lot of makedirs calls at page_q
        # population time, and assume dest's dir exists.
        os.makedirs(self.dest.parent, exist_ok=True)
        self.dest.write_bytes(r.content)


async def _main(*, manga_url, num_workers):
    # API v2 documentation can be read at https://api.mangadex.org/v2/
    # Last time I tried http2 client, it seemed not great.
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
            break  # just one chapter for now to iterate on downloading

    print(f"Found {chapter_q.qsize()} chapters (lang {lang}).")

    downloaders = dict()
    page_q = asyncio.Queue()

    # Consume from chapter_q, produce to page_q.
    async def page_worker():
        while True:
            try:
                chapter = chapter_q.get_nowait()
            except asyncio.QueueEmpty:
                return

            # TODO: pass cli option for data saver
            r = await api.get(f"/chapter/{chapter.id}", params={"saver": "false"})
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

                if dest_p.is_file():
                    print(f"Skipped {dest_p} because file exists.")
                    continue

                p = Page(
                    http_client=downloaders[server],
                    http_path=f"/{chapter_data['hash']}/{filename}",
                    dest=dest_p,
                )
                page_q.put_nowait(p)

    await asyncio.gather(*(page_worker() for _ in range(num_workers)))

    # Consume from page_q.
    async def downloader_worker():
        while True:
            try:
                page = page_q.get_nowait()
            except asyncio.QueueEmpty:
                return

            # TODO: If this fails, we shouldn't abort the whole program.
            # I think need to set return_exceptions=True on asyncio.gather
            # and iterate through the result list and report.
            await page.download()

    await asyncio.gather(*(downloader_worker() for _ in range(num_workers)))

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

    uvloop.install()
    asyncio.run(_main(manga_url=manga_url, num_workers=num_workers))

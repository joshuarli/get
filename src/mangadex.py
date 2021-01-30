import asyncio
import os
import sys
from pathlib import Path

import httpx
import uvloop

# Mangadex has "data saver" servers which serve pretty compressed images,
# I haven't yet figured out how to get it from their API.

# Right now it's pretty much sequential out of respect for mangadex.
# It's async because I copypasted from mangakakalot.


async def _main(*, page, workers):
    http = httpx.AsyncClient(timeout=None)
    lang = "gb"  # mangadex lang_name English

    print("Getting chapter list.")

    # https://mangadex.org/title/499/teppu/
    title_id = page.rstrip("/").split("/")[-2]
    r = await http.get(f"https://mangadex.org/api/manga/{title_id}")
    r.raise_for_status()
    data = r.json()

    title = data["manga"]["title"]
    title_p = Path(title)
    title_p.mkdir(exist_ok=True)

    chapters = sorted(
        filter(lambda x: x[1]["lang_code"] == lang, data["chapter"].items()),
        key=lambda x: x[1]["chapter"],
    )

    print(f"Found {len(chapters)} chapters (lang {lang}).")

    for chapter_id, chapter in chapters:
        chapter_no = chapter["chapter"]

        r = await http.get(f"https://mangadex.org/api/chapter/{chapter_id}")
        r.raise_for_status()
        data = r.json()
        # assert chapter_no == data["chapter"]

        chapter_p = title_p / chapter_no

        image_base_url = f"{data['server']}{data['hash']}/"
        downloads = []

        for page_name in data["page_array"]:
            image_p = chapter_p / page_name
            if image_p.is_file():
                print(f"{image_p} already exists; skipping.")
                continue

            image_src_url = image_base_url + page_name
            print(image_src_url, "->", image_p)
            downloads.append((image_src_url, str(image_p)))

        # TODO dest is not correcrtly relative
        # need to strip away title
        with open(title_p / "aria2c_downloads", mode="w") as f:
            f.writelines((f"{url}\n\tout={dest}\n" for url, dest in downloads))

    await http.aclose()


def main():
    # argparse todo
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

    uvloop.install()
    asyncio.run(_main(page=page, workers=num_workers))

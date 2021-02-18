import logging
import re
import sys
import time
from calendar import timegm
from hashlib import blake2b

import feedparser
import httpx

# This looks at podcast RSS feeds, and ingests it into a Meilisearch index.
# TODO: make async, 1 async worker for every feed
# TODO: store persistent state to resume from somewhere

audio_mime_ext = {
    "audio/mpeg": ".mp3",
    "audio/ogg": ".opus",
    "audio/flac": ".flac",
}

# meilisearch: a document primary key can be of type integer or string only
# composed of alphanumeric characters, hyphens (-) and underscores (_)
is_valid_pk = re.compile(r"^[A-Za-z0-9_-]+$")


def main():
    # TODO: argparse and #workers flag when async
    if len(sys.argv) < 2:
        sys.exit(f"""usage: {sys.argv[0]} RSS [RSS...]""")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)-8s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_main = logging.getLogger("main")

    db_client = httpx.Client(base_url="http://127.0.0.1:7700")

    try:
        resp = db_client.get("/health")
        resp.raise_for_status()
    except httpx.HTTPError:
        # As far as I've seen, at least ReadTimeout and ConnectTimeout are empty as str.
        # So, just repr them for now - but it'd be nice to contribute to upstream
        # to be more specific here.
        log_main.exception("meilisearch healthcheck failed!")
        sys.exit(1)

    for feed_url in sys.argv[1:]:
        # note: parse does accept remote urls, but we should offload this to async httpx
        feed = feedparser.parse(feed_url)

        podcast_title = feed.channel.title
        # TODO: ingest podcast metadata in the future
        # feed.channel.image
        # feed.channel.subtitle
        # Hmm, is feed.channel.published, feed.channel.updated of any use?
        log_main.info(f"Parsing {podcast_title}...")

        raw_episodes = feed.entries
        log_main.info(f"Found {len(raw_episodes)} episodes.")

        episodes = []
        for ep in raw_episodes:
            episode_data = {}

            title = ep.title or ep.itunes_title
            log_main.info(f"Parsing `{podcast_title}` episode '{title}'...")

            # We'll use this as the meilisearch pk for episodes.
            # https://itunespartner.apple.com/podcasts/articles/podcast-requirements-3058
            # "All episodes must contain a globally unique identifier (GUID), which never changes."
            pk = ep.id
            if is_valid_pk.match(pk) is None:
                log_main.info(
                    f"Found invalid pk `{pk}`, so generating a replacement checksum."
                )
                h = blake2b()
                h.update(f"{podcast_title} {title}".encode())
                pk = h.hexdigest()

            episode_data["id"] = pk

            # Audio source information.
            # I'm not sure how stable these URLs are. Might warrant a need to refresh.
            # It can also be found in ep.links filtering for rel = enclosure.
            # https://feedparser.readthedocs.io/en/latest/reference-entry-enclosures.html
            # States that some feeds break the RSS spec here,
            # we just assume the 1st item is the audio source.
            if len(ep.enclosures) > 1:
                # TODO: investigate if we break here
                breakpoint()

            mimetype = ep.enclosures[0].type
            ext = audio_mime_ext.get(mimetype, None)
            if ext is None:
                log_main.warning(f"Skipping due to unrecognized mimetype {mimetype}.")
                continue

            episode_data["audio_ext"] = ext
            episode_data["audio_src"] = ep.enclosures[0].href

            episode_data["title"] = title
            episode_data["podcast"] = podcast_title
            episode_data["description"] = ep.description
            episode_data["notes"] = ep.subtitle
            # https://feedparser.readthedocs.io/en/latest/date-parsing.html
            # This published_parsed is UTC, therefore we use calendar.timegm.
            episode_data["timestamp_published"] = timegm(ep.published_parsed)

            # optional information
            episode_data["duration"] = ep.get("itunes_duration", "")
            # you could in theory use publish date to logically determine this
            episode_data["episode_no"] = ep.get("itunes_episode", "")
            # are ep.tags useful?
            # ep.tags "terms"

            episodes.append(episode_data)

        # https://docs.meilisearch.com/reference/api/documents.html#add-or-replace-documents
        resp = db_client.put("/indexes/episodes/documents", json=episodes)
        resp.raise_for_status()
        update_id = resp.json()["updateId"]
        log_main.info(f"submitted update id {update_id}")

        # You have to inspect the update to see failure modes.
        # See: https://docs.meilisearch.com/learn/advanced/asynchronous_updates.html
        # Start delay 250ms, then exponentially backoff factor of 2, limit 1 minute ELASPED.
        wait, elasped = 250, 0
        while True:
            time.sleep(wait * 0.001)
            log_main.info(f"polling update id {update_id}")

            # TODO: make all of this more robust

            resp = db_client.get(f"/indexes/episodes/updates/{update_id}")
            resp.raise_for_status()
            status = resp.json()["status"]  # enqueued, processed, failed

            if status == "processed":
                log_main.info(f"update id {update_id} SUCCESS!")
                break
            elif status == "enqueued":
                pass
            elif status == "failed":
                log_main.error(f"update id {update_id} FAILED!")
                break
            else:
                # need to be more robust
                exit(f"update id {update_id} unexpected status: {status}")

            elasped += wait
            if elasped >= 60000:
                log_main.warning(
                    f"database update id {update_id}"
                    "taking longer than expected to succeed, giving up on checking it"
                )
                break

            wait *= 2

import re
import sys
import time
from calendar import timegm

import feedparser
import httpx

# This looks at podcast RSS feeds, and ingests it into a Meilisearch index.
# TODO: make async, 1 async worker for every feed
# TODO: store persistent state to resume from somewhere

# Note: there is a meilisearch python client, but my usage is fairly basic for now.

audio_mime_ext = {
    "audio/mpeg": ".mp3",
    "audio/ogg": ".opus",
    "audio/flac": ".flac",
}

# TODO: healthcheck would be cool to do on startup
db_client = httpx.Client(base_url="http://127.0.0.1:7700")

# meilisearch: a document primary key can be of type integer or string only
# composed of alphanumeric characters, hyphens (-) and underscores (_)
is_valid_pk = re.compile(r"^[A-Za-z0-9_-]+$")


def main():
    # TODO: argparse and #workers flag when async
    if len(sys.argv) < 2:
        sys.exit(f"""usage: {sys.argv[0]} RSS [RSS...]""")

    for feed_url in sys.argv[1:]:
        # note: parse does accept remote urls, but we should offload this to async httpx
        feed = feedparser.parse(feed_url)

        podcast_title = feed.channel.title
        # TODO: ingest podcast metadata in the future
        # feed.channel.image
        # feed.channel.subtitle
        print(f"Parsing {podcast_title}...")

        # Hmm, is feed.channel.published, feed.channel.updated of any use?

        raw_episodes = feed.entries
        print(f"Found {len(raw_episodes)} episodes.")

        episodes = []

        for ep in raw_episodes:
            episode_data = {}

            # Fallback to ep.itunes_title necessary?
            title = ep.title
            print(f"Parsing episode '{title}'...")

            # We'll use this as the meilisearch pk for episodes.
            # https://itunespartner.apple.com/podcasts/articles/podcast-requirements-3058
            # "All episodes must contain a globally unique identifier (GUID), which never changes."
            pk = ep.id
            if is_valid_pk.match(pk) is None:
                # TODO do this.
                print(
                    f"WARNING: found invalid pk `{pk}`, so generating a checksum as a replacement."
                )
                # breakpoint()
                continue

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
                print(f"Skipping due to unrecognized mimetype {mimetype}.")
                continue

            episode_data["audio_ext"] = ext
            episode_data["audio_src"] = ep.enclosures[0].href

            episode_data["title"] = title

            episode_data["description"] = ep.description
            episode_data["notes"] = ep.subtitle
            episode_data["author"] = ep.author

            # Some other information to enable in future:
            # ep.tags "terms"
            # ep.itunes_episode is this... canonical?
            # i suppose, could use publish date to logically determine this)

            # https://feedparser.readthedocs.io/en/latest/date-parsing.html
            # This published_parsed is UTC, therefore we use calendar.timegm.
            episode_data["timestamp_published"] = timegm(ep.published_parsed)

            # Interesting metadata to generate here would be to
            # actually async download and recompress the audio (2ch 96k opus)
            # and then update the relevant item with episode duration.
            # Wonder if the way to go here is to store the audio on disk
            # with meilisearch primary key as filename.
            # Also then, I wouldn't have to worry about audio source url getting stale.

            episodes.append(episode_data)

        # https://docs.meilisearch.com/reference/api/documents.html#add-or-replace-documents
        resp = db_client.put("/indexes/episodes/documents", json=episodes)
        resp.raise_for_status()
        update_id = resp.json()["updateId"]

        # You have to inspect the update to see failure modes.
        # See: https://docs.meilisearch.com/learn/advanced/asynchronous_updates.html
        time.sleep(1)
        resp = db_client.get(f"/indexes/episodes/updates/{update_id}")
        resp.raise_for_status()
        print(resp.json())

import sys
from calendar import timegm

import feedparser

# import httpx

# This looks at podcast RSS feeds, and ingests it into a Meilisearch index.
# TODO: make async, 1 async worker for every feed
# TODO: store persistent state to resume from somewhere

# Note: there is a meilisearch python client, but my usage is fairly basic for now.


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

        episodes = feed.entries
        print(f"Found {len(episodes)} episodes.")

        for ep in episodes:
            # Fallback to ep.itunes_title necessary?
            title = ep.title
            print(f"Parsing episode '{title}'...")

            description = ep.description
            notes = ep.subtitle
            author = ep.author

            # Audio source information.
            # I'm not sure how stable these URLs are. Might warrant a need to refresh.
            # It can also be found in ep.links filtering for rel = enclosure.
            # https://feedparser.readthedocs.io/en/latest/reference-entry-enclosures.html
            # States that some feeds break the RSS spec here,
            # we just assume the 1st item is the audio source.
            if len(ep.enclosures) > 1:
                # TODO: investigate if we break here
                breakpoint()
            url = ep.enclosures[0].href
            mimetype = ep.enclosures[0].type

            # Some other information to enable in future:
            # ep.tags "terms"
            # ep.itunes_episode is this... canonical? i suppose, could use publish date to logically determine this)

            # https://feedparser.readthedocs.io/en/latest/date-parsing.html
            # This published_parsed is UTC, therefore we use calendar.timegm.
            timestamp_published = timegm(ep.published_parsed)

            # Interesting metadata to generate here would be to
            # actually async download and recompress the audio (2ch 96k opus)
            # and then update the relevant item with episode duration.
            # Wonder if the way to go here is to store the audio on disk
            # with meilisearch primary key as filename.
            # Also then, I wouldn't have to worry about audio source url getting stale.

            # Todo, ingest this.
            print(description, notes, author, url, mimetype, timestamp_published)

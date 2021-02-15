from setuptools import setup


def get_requirements(suffix=""):
    with open(f"requirements{suffix}.txt") as f:
        return [x for x in f.read().strip().split("\n") if not x.startswith("#")]


setup(
    name="get",
    version="0.0.0",
    author="joshuarli",
    entry_points={
        "console_scripts": [
            "get-mangadex=src.mangadex:main",
            "get-podcasts-ingest-rss=src.podcasts.rss:main",
        ]
    },
    python_requires=">=3.7",
    install_requires=get_requirements(),
    extras_require={"dev": get_requirements("-dev")},
)

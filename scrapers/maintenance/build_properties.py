"""Build the property tables from the raw archive. Nothing is downloaded.

Run from scrapers/, after a crawl or a parser fix:

    uv run python -m maintenance.build_properties

It takes the newest archived page of each parcel seen in the latest finished
`vgsi_property` crawl, parses it, runs the quality checks, and replaces `properties`
and `property_sales` in one transaction. When a check fails it writes nothing, logs
why, and exits 1.
"""

import argparse
import sys
from collections.abc import Sequence

import logfire
from bootstrap import bootstrap
from ingest.properties import BuildResult, build
from mongo.archive import RawArchive, archive_collection
from mongo.client import get_db
from postgres import open_session


def main(argv: Sequence[str] | None = None) -> int:
    bootstrap("build-properties")
    # It takes no options, but parsing makes --help print usage instead of building.
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)

    with open_session() as session:
        result = build(session, RawArchive(archive_collection(get_db())))

    if result.run_id is None:
        logfire.error("no finished crawl of vgsi_property; run the crawl first")
        print(
            "No finished crawl of vgsi_property. Run the crawl first.", file=sys.stderr
        )
        return 1
    print("\n".join(_check_lines(result)))
    if result.failed:
        print(f"Nothing written. The tables still hold {result.current} parcels.")
        return 1
    print(
        f"Built {result.parcels} parcels and {result.sales} sales from crawl run "
        f"{result.run_id}. {result.unparsed} pages did not parse, and "
        f"{result.without_mblu} had no mblu."
    )
    return 0


def _check_lines(result: BuildResult) -> list[str]:
    return [
        f"{'ok  ' if check.passed else 'FAIL'} {check.name}: {check.detail}"
        for check in result.checks
    ]


if __name__ == "__main__":
    sys.exit(main())

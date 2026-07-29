import argparse
import logging
import sys

from app.lib.builder import StoreBuilder
from app.lib.updater import CollectionUpdater

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_headers(headers_str: str) -> list[tuple[str, str]]:
    """Parse header string like '#:H1,##:H2,###:H3' into list of tuples."""

    def parse_item(item: str) -> tuple[str, str]:
        if ":" not in item:
            raise argparse.ArgumentTypeError(
                f"Invalid header format '{item}'. Expected 'prefix:label'."
            )
        prefix, label = item.split(":", 1)
        if not prefix.strip() or not label.strip():
            raise argparse.ArgumentTypeError(
                f"Invalid header format '{item}'. Both prefix and label must be non-empty."
            )
        return prefix.strip(), label.strip()

    return [parse_item(item.strip()) for item in headers_str.split(",")]


def cmd_build(args: argparse.Namespace) -> None:
    """Execute the build command."""
    headers = None
    if args.headers:
        headers = parse_headers(args.headers)

    builder = StoreBuilder(
        data_dir=args.data_dir,
        collection_name=args.collection,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        headers_to_split_on=headers,
        reset=args.reset,
    )

    summary = builder.build(build_bm25=not args.no_bm25, show_progress=not args.quiet)

    if summary["files"] == 0:
        logger.warning("No files found. Nothing was ingested.")
        sys.exit(1)

    print(f"\nBuild complete:")
    print(f"  Files processed:  {summary['files']}")
    print(f"  Chunks ingested:  {summary['chunks']}")
    print(f"  Collection: {summary['collection']}")
    if "bm25_index" in summary:
        print(f"  BM25 index: {summary['bm25_index']}")


def cmd_add(args: argparse.Namespace) -> None:
    """Execute the add command."""
    headers = None
    if args.headers:
        headers = parse_headers(args.headers)

    updater = CollectionUpdater(
        collection_name=args.collection,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        headers_to_split_on=headers,
    )

    summary = updater.add_documents(
        args.data_dir, build_bm25=not args.no_bm25, show_progress=not args.quiet
    )

    if summary.get("files", 0) == 0:
        logger.warning("No files found. Nothing was added.")
        sys.exit(1)

    print(f"\nAdd complete:")
    print(f"  Files processed:  {summary['files']}")
    print(f"  Chunks added:      {summary['chunks']}")
    print(f"  Collection: {summary['collection']}")
    if "bm25_index" in summary:
        print(f"  BM25 index: {summary['bm25_index']}")


def cmd_delete(args: argparse.Namespace) -> None:
    """Execute the delete command."""
    updater = CollectionUpdater(collection_name=args.collection)
    result = updater.delete_collection()
    print(f"\nDeleted collection: {result['collection']}")
    print(f"  BM25 index deleted: {result['bm25_index_deleted']}")


def cmd_build_faq(args: argparse.Namespace) -> None:
    """Execute the build-faq command."""
    from app.lib.suggester import FAQBuilder

    builder = FAQBuilder(reset=args.reset, show_progress=not args.quiet)
    result = builder.build()
    print(f"\nFAQ collection built:")
    print(f"  Questions: {result['questions']}")
    print(f"  Collection: {result['collection']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="CTU AI Context Search - Vector Store CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser(
        "build", help="Build vector store from markdown files"
    )
    build_parser.add_argument(
        "--data-dir",
        required=True,
        help="Path to folder containing .md files (searched recursively).",
    )
    build_parser.add_argument(
        "--collection",
        required=True,
        help="Collection name for the vector store.",
    )
    build_parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Chunk size for text splitting (default: 1000).",
    )
    build_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help="Chunk overlap for text splitting (default: 100).",
    )
    build_parser.add_argument(
        "--headers",
        default=None,
        help='Markdown headers to split on, e.g. "#:H1,##:H2,###:H3".',
    )
    build_parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collections before rebuilding.",
    )
    build_parser.add_argument(
        "--no-bm25",
        action="store_true",
        help="Skip BM25 index building (dense vectors only).",
    )
    build_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress bar output.",
    )
    build_parser.set_defaults(func=cmd_build)

    add_parser = subparsers.add_parser(
        "add", help="Add new markdown files to an existing collection"
    )
    add_parser.add_argument(
        "--data-dir",
        required=True,
        help="Path to folder containing .md files (searched recursively).",
    )
    add_parser.add_argument(
        "--collection",
        required=True,
        help="Existing collection name to add documents to.",
    )
    add_parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Chunk size for text splitting (default: 1000).",
    )
    add_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help="Chunk overlap for text splitting (default: 100).",
    )
    add_parser.add_argument(
        "--headers",
        default=None,
        help='Markdown headers to split on, e.g. "#:H1,##:H2,###:H3".',
    )
    add_parser.add_argument(
        "--no-bm25",
        action="store_true",
        help="Skip BM25 index update (dense vectors only).",
    )
    add_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress bar output.",
    )
    add_parser.set_defaults(func=cmd_add)

    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete a collection and its associated BM25 index",
    )
    delete_parser.add_argument(
        "--collection",
        required=True,
        help="Collection name to delete.",
    )
    delete_parser.set_defaults(func=cmd_delete)

    build_faq_parser = subparsers.add_parser(
        "build-faq", help="Build FAQ collection for similar question suggestions"
    )
    build_faq_parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing FAQ collection before rebuilding.",
    )
    build_faq_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress bar output.",
    )
    build_faq_parser.set_defaults(func=cmd_build_faq)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

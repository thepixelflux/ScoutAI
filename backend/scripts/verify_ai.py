"""Verify both real LLM calls and embedding retrieval, without accepting fallback."""
import argparse
from . import verify_embeddings, verify_provider

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--llm-only', action='store_true')
    group.add_argument('--embedding-only', action='store_true')
    args = parser.parse_args()
    if not args.embedding_only: verify_provider.main()
    if not args.llm_only: verify_embeddings.main()
if __name__ == '__main__': main()

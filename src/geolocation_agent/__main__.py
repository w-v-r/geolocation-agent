"""CLI entry point for the geolocation agent."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Geolocation Agent - Find where a photo was taken")
    parser.add_argument("image_path", help="Path to the image to investigate")
    parser.add_argument(
        "--side-info", default="", help="Additional context about the image",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None, help="Max investigation iterations",
    )
    parser.add_argument("--provider", choices=["openai", "anthropic", "google"], default=None,
                        help="LLM provider to use")

    args = parser.parse_args()

    if args.provider:
        import os
        os.environ["LLM_PROVIDER"] = args.provider

    from geolocation_agent.agent import run_investigation

    print(f"Investigating: {args.image_path}")
    if args.side_info:
        print(f"Side info: {args.side_info}")
    print("-" * 60)

    result = run_investigation(
        image_path=args.image_path,
        side_info=args.side_info,
        max_iterations=args.max_iterations,
    )

    final_answer = result.get("final_answer")
    if final_answer:
        print("\n" + "=" * 60)
        print("INVESTIGATION COMPLETE")
        print("=" * 60)

        best = final_answer.get("best_candidate")
        if best:
            print(f"\nBest candidate: {best.get('name', 'Unknown')}")
            if best.get("latitude") and best.get("longitude"):
                print(f"Coordinates: ({best['latitude']}, {best['longitude']})")
            if best.get("address"):
                print(f"Address: {best['address']}")
            print(f"Confidence: {best.get('confidence', 0):.0%}")

        print(f"\nRegion confidence: {final_answer.get('region_confidence', '?')}")
        print(f"Place type confidence: {final_answer.get('place_type_confidence', '?')}")
        print(f"Venue confidence: {final_answer.get('venue_confidence', '?')}")

        key_evidence = final_answer.get("key_evidence", [])
        if key_evidence:
            print("\nKey evidence:")
            for ev in key_evidence:
                print(f"  + {ev}")

        alternatives = final_answer.get("alternative_candidates", [])
        if alternatives:
            print("\nAlternative candidates:")
            for alt in alternatives:
                print(f"  - {alt.get('name', '?')} (confidence: {alt.get('confidence', 0):.0%})")

        print(f"\nReasoning summary:\n{final_answer.get('reasoning_summary', '')}")
    else:
        print("\nNo final answer produced.")
        print(f"Iterations completed: {result.get('iteration', 0)}")


if __name__ == "__main__":
    main()

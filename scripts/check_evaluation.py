"""Verify saved evaluation evidence read-only and print its scoring report."""
import argparse
import json

from core.evaluation_evidence import EvaluationEvidenceClient


class EvaluationCheck:
    """Report consistency separately from whether a strategy improved."""

    def __init__(self, client=None):
        self.client = client if client is not None else EvaluationEvidenceClient()

    def run(self, directory):
        report = self.client.verify(directory)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return 1 if report["decision"] == "INCONCLUSIVE" else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="Directory containing manifest.json and attempt artifacts")
    args = parser.parse_args(argv)
    return EvaluationCheck().run(args.directory)


if __name__ == "__main__":
    raise SystemExit(main())

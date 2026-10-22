import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import stoneart_blog


class RedirectCheckTests(unittest.TestCase):
    def test_redirect_target_matches_same_path_and_query(self):
        self.assertTrue(
            stoneart_blog.redirect_targets_match(
                "https://www.stoneartsculpture.com/blog/new-guide/?ref=old",
                "https://www.stoneartsculpture.com/blog/new-guide/?ref=old",
            )
        )

    def test_redirect_target_rejects_wrong_path_host_or_query(self):
        expected = "https://www.stoneartsculpture.com/blog/new-guide/"
        for actual in (
            "https://www.stoneartsculpture.com/blog/other-guide/",
            "https://example.com/blog/new-guide/",
            "https://www.stoneartsculpture.com/blog/new-guide/?ref=wrong",
        ):
            self.assertFalse(stoneart_blog.redirect_targets_match(actual, expected))


if __name__ == "__main__":
    unittest.main()

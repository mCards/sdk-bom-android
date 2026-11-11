import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import release


class ReleaseTests(unittest.TestCase):
    def test_bom_changes_only_publication_coordinates(self):
        pom = b'''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>com.mcards.sdk</groupId><artifactId>bom-internal</artifactId><version>1.0.19.26</version>
<dependencyManagement><dependencies><dependency><groupId>com.mcards.sdk</groupId><artifactId>cards</artifactId><version>1.2.0</version></dependency></dependencies></dependencyManagement></project>'''
        module = {"component": {"group": "com.mcards.sdk", "module": "bom-internal", "version": "1.0.19.26"},
                  "variants": [{"dependencyConstraints": [{"module": "cards", "version": {"strictly": "1.2.0"}}]}]}
        output_pom, output_module = release.rewrite_bom(pom, json.dumps(module).encode(), "1.0.19")
        output = json.loads(output_module)
        self.assertEqual(output["variants"], module["variants"])
        self.assertEqual(output["component"]["module"], "bom")
        self.assertEqual(output["component"]["version"], "1.0.19")
        self.assertIn(b"published-with-gradle-metadata", output_pom)
        release.validate_bom(output_pom, [{"group": "com.mcards.sdk", "name": "cards", "version": "1.2.0"}])
        with self.assertRaises(ValueError):
            release.validate_bom(output_pom, [{"group": "com.mcards.sdk", "name": "cards", "version": "1.1.10.0"}])

    def test_lock_detects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item = {"group": "com.mcards.sdk", "name": "cards", "version": "1.2.0", "files": ["cards-1.2.0.aar"]}
            path = root / release.coordinate_path(item) / item["files"][0]
            path.parent.mkdir(parents=True)
            path.write_bytes(b"approved")
            lock = root / "lock.json"
            release.check_lock([item], root, lock, write=True)
            release.check_lock([item], root, lock)
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                release.check_lock([item], root, lock)

    def test_source_artifact_hash_must_match_metadata(self):
        item = {"group": "com.mcards.sdk", "name": "cards", "version": "1.2.0", "repository": "Wantsa/sdk-cards-android"}
        pom = b'<project xmlns="http://maven.apache.org/POM/4.0.0"><packaging>aar</packaging></project>'
        module = json.dumps({"variants": [{"files": [{"url": "cards-1.2.0.aar", "sha256": hashlib.sha256(b"expected").hexdigest()}]}]}).encode()
        with tempfile.TemporaryDirectory() as temporary, patch.object(release, "download", side_effect=[pom, module, b"tampered"]):
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                release.stage_item(item, Path(temporary), "user", "token")

    def test_rejects_metadata_path_traversal(self):
        item = {"group": "com.mcards.sdk", "name": "cards", "version": "1.2.0", "repository": "Wantsa/sdk-cards-android"}
        pom = b'<project xmlns="http://maven.apache.org/POM/4.0.0"><packaging>aar</packaging></project>'
        module = json.dumps({"variants": [{"files": [{"url": "../outside.aar"}]}]}).encode()
        with tempfile.TemporaryDirectory() as temporary, patch.object(release, "download", side_effect=[pom, module]):
            with self.assertRaisesRegex(ValueError, "Unexpected artifact path"):
                release.stage_item(item, Path(temporary), "user", "token")

    def test_partial_customer_release_is_not_overwritten(self):
        item = {"group": "com.mcards.sdk", "name": "cards", "version": "1.2.0", "files": ["cards.pom", "cards.aar"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / release.coordinate_path(item)
            directory.mkdir(parents=True)
            for filename in item["files"]:
                (directory / filename).write_bytes(b"expected")
            with patch.object(release, "download", side_effect=[b"expected", None]):
                with self.assertRaisesRegex(ValueError, "Partial customer release"):
                    release.already_published(item, root, "user", "token")
            with patch.object(release, "download", side_effect=[b"different"]):
                with self.assertRaisesRegex(ValueError, "Existing customer artifact differs"):
                    release.already_published(item, root, "user", "token")
            with patch.object(release, "download", side_effect=[b"expected", b"expected"]):
                self.assertTrue(release.already_published(item, root, "user", "token"))


if __name__ == "__main__":
    unittest.main()


import unittest
from mod_support_check import (
    pcl_version_to_drop,
    pcl_drop_to_version,
    pcl_is_format_fit,
    extract_minecraft_constraints_forge_toml,
    is_version_supported,
    simple_toml_parse
)

class TestPCLVersion(unittest.TestCase):
    def test_version_to_drop(self):
        self.assertEqual(pcl_version_to_drop("1.20.1"), 200)
        self.assertEqual(pcl_version_to_drop("1.16.5"), 160)
        self.assertEqual(pcl_version_to_drop("1.7.10"), 70)
        self.assertEqual(pcl_version_to_drop("26.1"), 261)
        self.assertEqual(pcl_version_to_drop("1.20"), 200)
        # Snapshot
        self.assertEqual(pcl_version_to_drop("1.20.1-pre1"), 0)
        self.assertEqual(pcl_version_to_drop("1.20.1-pre1", allow_snapshot=True), 200)

    def test_drop_to_version(self):
        self.assertEqual(pcl_drop_to_version(200), "1.20")
        self.assertEqual(pcl_drop_to_version(160), "1.16")
        self.assertEqual(pcl_drop_to_version(261), "26.1")

    def test_forge_toml_parsing(self):
        toml_text = """
[[mods]]
modId="examplemod"
version="1.0.0"
displayName="Example Mod"

[[dependencies.examplemod]]
    modId="minecraft"
    mandatory=true
    versionRange="[1.16.5,1.17)"
    ordering="NONE"
    side="BOTH"
"""
        constraint = extract_minecraft_constraints_forge_toml(toml_text)
        self.assertEqual(constraint, "[1.16.5,1.17)")

        # Test multiple ranges
        toml_text_multi = """
[[dependencies.mod]]
    modId="minecraft"
    versionRange="[1.16.5]"
[[dependencies.mod]]
    modId="minecraft"
    versionRange="[1.18.2]"
"""
        constraint_multi = extract_minecraft_constraints_forge_toml(toml_text_multi)
        # My implementation joins with " || "
        self.assertTrue("[1.16.5]" in constraint_multi)
        self.assertTrue("[1.18.2]" in constraint_multi)

    def test_is_version_supported(self):
        # Range [1.16.5, 1.17)
        c = "[1.16.5,1.17)"
        self.assertTrue(is_version_supported("1.16.5", c))
        self.assertTrue(is_version_supported("1.16.9", c))
        self.assertFalse(is_version_supported("1.17.0", c))
        self.assertFalse(is_version_supported("1.16.4", c))

        # Range [1.20, 1.21)
        c2 = "[1.20,1.21)"
        self.assertTrue(is_version_supported("1.20.1", c2))
        
        # Exact
        c3 = "1.20.1"
        self.assertTrue(is_version_supported("1.20.1", c3))
        # PCL might treat 1.20.1 as 1.20.1 or prefix?
        # My match_token uses startswith for simple string
        self.assertTrue(is_version_supported("1.20.1", "1.20"))

if __name__ == "__main__":
    unittest.main()

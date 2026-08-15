import subprocess
import sys
import unittest


class ModelMetadataTests(unittest.TestCase):
    def test_assets_router_loads_referenced_project_table(self):
        command = (
            "from app.routers.assets import run_dialogue_analysis; "
            "from app.database import Base; "
            "assert 'assets' in Base.metadata.tables; "
            "assert 'projects' in Base.metadata.tables"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", command],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

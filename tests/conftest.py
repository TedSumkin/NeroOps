import os
import tempfile
from pathlib import Path

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="neroops-tests-"))
os.environ["NEROOPS_DATA_DIR"] = str(TEST_DATA_DIR)

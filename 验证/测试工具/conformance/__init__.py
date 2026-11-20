"""智慧教学-数据模型标准：合成符合性观察工具。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT.parent / "契约"
sys.path.insert(0, str(CONTRACT / "tools"))
from validate import validate

__version__ = "0.1.0"

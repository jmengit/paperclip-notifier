from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

ET.parse("unraid-template.xml")
yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
yaml.safe_load(Path("compose.yaml").read_text(encoding="utf-8"))
print("config.example.yaml, compose.yaml, and unraid-template.xml validated")

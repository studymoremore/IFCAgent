import os
from pathlib import Path

# --- Neo4j 连接配置 ---
# 如果是本地安装的 Neo4j，默认地址通常也是 bolt://localhost:7687
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_password"  # 请替换为你的密码

# --- 路径配置 ---
# 使用相对路径，确保在任何人的电脑上都能运行
BASE_DIR = Path(__file__).parent / "processed_downloaded_pages_json"
EXPERT_DIR = BASE_DIR / "expert"
ORG_DIR = BASE_DIR / "organization"
PATENT_DIR = BASE_DIR / "patent"
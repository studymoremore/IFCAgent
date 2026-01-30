import json
from pathlib import Path

class DataExtractor:
    def __init__(self, expert_dir, org_dir, patent_dir):
        self.expert_dir = expert_dir
        self.org_dir = org_dir
        self.patent_dir = patent_dir
        self.org_name_to_id = {} # 建立组织名到ID的映射

    def build_org_map(self):
        """建立 组织名称 -> ID 的映射表"""
        print("正在建立组织映射表...")
        for file in self.org_dir.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f).get("data", {})
                if data.get("id") and data.get("title"):
                    self.org_name_to_id[data["title"]] = data["id"]
        return self.org_name_to_id

    def get_experts(self):
        for file in self.expert_dir.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                yield json.load(f).get("data", {})

    def get_organizations(self):
        for file in self.org_dir.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                yield json.load(f).get("data", {})

    def get_patents(self):
        for file in self.patent_dir.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                yield json.load(f).get("data", {})
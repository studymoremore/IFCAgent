"""
数据加载工具

用于从本地加载项目需求和专家数据
"""

import json
import os
from typing import Dict, List


def load_project_requirements(data_path: str) -> List[Dict]:
    """
    从本地加载项目需求数据
    """
    projects = []
    
    if os.path.exists(data_path):
        if data_path.endswith('.json'):
            with open(data_path, 'r', encoding='utf-8') as f:
                projects = json.load(f)
    
    return projects


def load_expert_candidates(project_id: str, data_path: str, top_k: int = 20) -> List[Dict]:
    """
    加载某个项目的候选专家数据
    """
    experts = []
    
    return experts


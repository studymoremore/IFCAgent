import argparse
import json
import os
import sys
from pathlib import Path
from neo4j import GraphDatabase

# 添加项目根目录到Python路径，确保可以正确导入模块
# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录（当前文件的父目录的父目录）
project_root = os.path.dirname(os.path.dirname(current_dir))
# 将项目根目录添加到sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 请确保 config.py 中定义了 EXPERT_DIR, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from config.config import KG_CONFIG
NEO4J_URI = KG_CONFIG['NEO4J_URI']
NEO4J_USER = KG_CONFIG['NEO4J_USER']
NEO4J_PASSWORD = KG_CONFIG['NEO4J_PASSWORD']
EXPERT_DIR = KG_CONFIG['EXPERT_DIR']
ORG_DIR = KG_CONFIG['ORG_DIR']
PATENT_DIR = KG_CONFIG['PATENT_DIR']

class KGTool:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def run_query(self, cypher, params=None):
        with self.driver.session() as session:
            return list(session.run(cypher, params))

    def _get_keywords_from_json(self, name):
        """
        修正后的关键词提取函数
        精准路径：data -> ai_fields -> 专家简介 -> 综合分析 -> technical_keywords
        """
        file_path = Path(EXPERT_DIR) / f"{name}.json"
        
        if not file_path.exists():
            return set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # 严格按照数据实际层级进行链式安全提取
            keywords = raw_data.get('data', {}) \
                              .get('ai_fields', {}) \
                              .get('专家简介', {}) \
                              .get('综合分析', {}) \
                              .get('technical_keywords', [])
            
            # 确保返回的是集合(set)类型，以便后续进行 intersection (交集) 运算
            return set(keywords) if isinstance(keywords, list) else set()
        except Exception as e:
            # 如需调试，可以取消下面这一行的注释
            # print(f"解析 {name}.json 时出错: {e}")
            return set()

    def show_info(self, name):
        """查询专家的基础关联信息"""
        print(f"\n>>> 正在查询专家 [{name}] 的详细关联...")
        cypher = """
        MATCH (e:Expert {name: $name})
        OPTIONAL MATCH (e)-[:BELONGS_TO]->(o:Organization)
        OPTIONAL MATCH (e)-[:INVENTED]->(p:Patent)
        RETURN o.name as org, collect(DISTINCT p.name) as patents
        """
        records = self.run_query(cypher, {"name": name})
        if not records:
            print(f"未找到专家: {name}")
            return
        
        for rec in records:
            print(f"【所属组织】: {rec['org'] if rec['org'] else '未知'}")
            patents = rec['patents']
            print(f"【发明专利】(共 {len(patents)} 项):")
            for i, p_name in enumerate(patents, 1):
                print(f"  {i}. {p_name}")

    def find_social(self, name, relation_type):
        """查询合作伙伴或同事，字典格式呈现"""
        rel_map = {"partners": "COLLABORATED_WITH", "colleagues": "IS_COLLEAGUE_OF"}
        rel_label = "合作伙伴" if relation_type == "partners" else "同事"
        
        cypher = f"""
        MATCH (e:Expert {{name: $name}})-[:{rel_map[relation_type]}]-(other:Expert)
        RETURN other.name as name, other.id as id
        """
        records = self.run_query(cypher, {"name": name})
        result_dict = {str(rec['id']): rec['name'] for rec in records}
        print(f"【{rel_label}总数】: {len(result_dict)}")
        print(f"【列表明细】: {json.dumps(result_dict, ensure_ascii=False)}")

    def recommend_similar_experts(self, name, top_n=5):
        """混合检索：基于本地JSON技术栈在社交圈内推荐"""
        print(f"\n>>> 正在检索与 [{name}] 技术能力最相似的专家...")

        # 1. 获取自己的技术栈
        my_stack = self._get_keywords_from_json(name)
        if not my_stack:
            print(f"警告：无法从本地提取专家 [{name}] 的技术关键词，请确认 JSON 文件层级。")
            return

        # 2. 从图数据库获取社交圈及关系
        cypher = """
        MATCH (me:Expert {name: $name})-[r:COLLABORATED_WITH|IS_COLLEAGUE_OF]-(other:Expert)
        RETURN other.name as name, other.id as id, collect(DISTINCT type(r)) as rel_types
        """
        friends = self.run_query(cypher, {"name": name})
        
        if not friends:
            print("该专家在社交网络中暂无关联（同事或合伙人）。")
            return

        # 3. 匹配计算
        results = []
        for f in friends:
            f_name = f['name']
            f_stack = self._get_keywords_from_json(f_name)
            common = my_stack.intersection(f_stack)
            
            if common:
                results.append({
                    "name": f_name,
                    "id": f['id'],
                    "rel_types": f['rel_types'],
                    "common": list(common),
                    "score": len(common)
                })

        # 4. 排序输出
        results.sort(key=lambda x: x['score'], reverse=True)
        
        if not results:
            print("在社交圈中未发现技术关键词重合的专家。")
            return

        print(f"找到以下 {len(results[:top_n])} 位技术最相关的专家：")
        print("=" * 65)
        rel_map = {"IS_COLLEAGUE_OF": "同事", "COLLABORATED_WITH": "合作伙伴"}
        for i, res in enumerate(results[:top_n], 1):
            rels = " & ".join([rel_map.get(r, r) for r in res['rel_types']])
            print(f"{i}. 【{res['name']}】 (ID: {res['id']})")
            print(f"   ├─ 专家关系: {rels}")
            print(f"   ├─ 共同关键词 ({res['score']}个): {'、'.join(res['common'])}")
            print("-" * 65)

    def find_path(self, start_name, end_name):
        """路径查询（强制通过组织/专利中转）"""
        cypher = """
        MATCH (s:Expert {name: $s}), (e:Expert {name: $e})
        MATCH p = shortestPath((s)-[r*..10]-(e))
        WHERE ALL(rel IN relationships(p) WHERE type(rel) <> 'COLLABORATED_WITH' AND type(rel) <> 'IS_COLLEAGUE_OF')
        RETURN p
        """
        records = self.run_query(cypher, {"s": start_name, "e": end_name})
        if not records:
            print("未找到中转关联路径。")
            return
        path = records[0]['p']
        steps = [f"[{list(n.labels)[0]}]{n['name']}" for n in path.nodes]
        print(" -> ".join(steps))

def main():
    parser = argparse.ArgumentParser(description="Expert KG Tool V2.2")
    parser.add_argument("--name", type=str, help="目标专家姓名")
    parser.add_argument("--action", choices=["info", "partners", "colleagues", "recommend"])
    parser.add_argument("--path", nargs=2, metavar=('START', 'END'))

    args = parser.parse_args()
    tool = KGTool()

    try:
        if args.path:
            tool.find_path(args.path[0], args.path[1])
        elif args.name and args.action:
            if args.action == "info": tool.show_info(args.name)
            elif args.action == "recommend": tool.recommend_similar_experts(args.name)
            else: tool.find_social(args.name, args.action)
        else:
            parser.print_help()
    finally:
        tool.close()

if __name__ == "__main__":
    main()
"""
知识图谱检索工具

从知识图谱中检索路径，并将检索到的路径转化为自然语言描述
"""

import sys
import os
from pathlib import Path
import json
import json5
from neo4j import GraphDatabase
from qwen_agent.tools.base import BaseTool, register_tool

# 添加 knowledge_graph/kg_build 目录到路径，以便导入 config
current_dir = Path(__file__).parent
kg_build_dir = current_dir.parent / "knowledge_graph" / "kg_build"
if str(kg_build_dir) not in sys.path:
    sys.path.insert(0, str(kg_build_dir))

# 导入知识图谱配置
try:
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EXPERT_DIR
except ImportError:
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "sysu_wang_wu"
    EXPERT_DIR = kg_build_dir / "processed_downloaded_pages_json" / "expert"


@register_tool('kg_retrieval')
class KGRetrieval(BaseTool):
    """知识图谱检索工具"""
    
    description = '从知识图谱中检索实体间的路径关系（如专家-专利-专家合作者关系、专家-组织-专家同事关系），并将检索到的路径转化为自然语言描述。支持三种查询模式：1) 路径查询：指定source_entity和target_entity查询两个专家之间的关联路径；2) 邻居查找：指定source_entity和relation_type（coauthor=合作者，colleague=同事）查找专家的合作伙伴或同事；3) 相似专家推荐：只指定source_entity，基于技术关键词推荐相似专家。'
    
    parameters = [{
        'name': 'source_entity',
        'type': 'string',
        'description': '源实体ID或名称（如专家姓名）',
        'required': True
    }, {
        'name': 'target_entity',
        'type': 'string',
        'description': '目标实体ID或名称（如专家姓名），如果为空则检索源实体的所有相关路径',
        'required': False
    }, {
        'name': 'relation_type',
        'type': 'string',
        'description': '关系类型：coauthor（合作者，通过专利）、colleague（同事，通过组织），如果为空则检索所有关系',
        'required': False
    }, {
        'name': 'max_path_length',
        'type': 'integer',
        'description': '最大路径长度（跳数），默认10',
        'required': False
    }]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        except Exception as e:
            print(f"警告：无法连接到 Neo4j 数据库: {e}")
            self.driver = None
    
    def _run_query(self, cypher, params=None):
        """执行 Cypher 查询"""
        if not self.driver:
            return []
        try:
            with self.driver.session() as session:
                return list(session.run(cypher, params))
        except Exception as e:
            if os.getenv('DEBUG_KG_RETRIEVAL', 'False').lower() == 'true':
                print(f"[KG工具调试] 查询执行失败: {str(e)}")
            return []
    
    def _get_keywords_from_json(self, name):
        """从 JSON 文件中提取专家的技术关键词"""
        file_path = Path(EXPERT_DIR) / f"{name}.json"
        if not file_path.exists():
            return set()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            keywords = raw_data.get('data', {}).get('ai_fields', {}).get('专家简介', {}).get('综合分析', {}).get('technical_keywords', [])
            return set(keywords) if isinstance(keywords, list) else set()
        except Exception:
            return set()
    
    def find_path(self, start_name, end_name, max_length=10):
        """路径查询（强制通过组织/专利中转）"""
        cypher = f"""
        MATCH (s:Expert {{name: $s}}), (e:Expert {{name: $e}})
        MATCH p = shortestPath((s)-[r*..{max_length}]-(e))
        WHERE ALL(rel IN relationships(p) WHERE type(rel) <> 'COLLABORATED_WITH' AND type(rel) <> 'IS_COLLEAGUE_OF')
        RETURN p
        LIMIT 1
        """
        records = self._run_query(cypher, {"s": start_name, "e": end_name})
        if not records:
            return {
                'found': False,
                'path': None,
                'path_string': None,
                'natural_language': f"未找到从 {start_name} 到 {end_name} 的中转关联路径"
            }
        
        path = records[0]['p']
        nodes = []
        for node in path.nodes:
            try:
                node_name = node['name']
            except (KeyError, TypeError, AttributeError):
                try:
                    node_name = dict(node).get('name', '')
                except:
                    node_name = getattr(node, 'name', '') if hasattr(node, 'name') else ''
            nodes.append({
                'name': node_name,
                'type': list(node.labels)[0] if list(node.labels) else 'Unknown'
            })
        
        path_steps = [f"[{n['type']}]{n['name']}" for n in nodes]
        path_string = " -> ".join(path_steps)
        natural_language = self._path_to_natural_language_from_neo4j_path(path)
        
        return {
            'found': True,
            'path': {'nodes': nodes, 'relationships': [rel.type for rel in path.relationships]},
            'path_string': path_string,
            'natural_language': natural_language
        }
    
    def find_social(self, name, relation_type):
        """查询合作伙伴或同事"""
        rel_map = {"coauthor": "COLLABORATED_WITH", "colleague": "IS_COLLEAGUE_OF"}
        rel_label_map = {"coauthor": "合作伙伴", "colleague": "同事"}
        
        if relation_type not in rel_map:
            return {'found': False, 'neighbors': [], 'count': 0, 'message': f'不支持的关系类型: {relation_type}'}
        
        cypher = f"""
        MATCH (e:Expert {{name: $name}})-[:{rel_map[relation_type]}]-(other:Expert)
        RETURN other.name as name, other.id as id
        """
        records = self._run_query(cypher, {"name": name})
        neighbors = []
        for rec in records:
            try:
                neighbor_name = rec.get('name', '')
                if neighbor_name:
                    neighbors.append({"id": str(rec.get('id', '')), "name": neighbor_name})
            except:
                continue
        
        return {
            'found': True,
            'neighbors': neighbors,
            'count': len(neighbors),
            'relation_type': relation_type,
            'relation_label': rel_label_map[relation_type],
            'message': f'找到 {len(neighbors)} 个{rel_label_map[relation_type]}'
        }
    
    def recommend_similar_experts(self, name, top_n=5):
        """混合检索：基于本地JSON技术栈在社交圈内推荐相似专家"""
        my_stack = self._get_keywords_from_json(name)
        if not my_stack:
            return {'found': False, 'recommendations': [], 'message': f'无法从本地提取专家 [{name}] 的技术关键词'}
        
        cypher = """
        MATCH (me:Expert {name: $name})-[r:COLLABORATED_WITH|IS_COLLEAGUE_OF]-(other:Expert)
        RETURN other.name as name, other.id as id, collect(DISTINCT type(r)) as rel_types
        """
        friends = self._run_query(cypher, {"name": name})
        if not friends:
            return {'found': False, 'recommendations': [], 'message': '该专家在社交网络中暂无关联（同事或合伙人）'}
        
        results = []
        for f in friends:
            try:
                f_name = f.get('name', '')
                if not f_name:
                    continue
                f_stack = self._get_keywords_from_json(f_name)
                common = my_stack.intersection(f_stack)
                if common:
                    rel_map = {"IS_COLLEAGUE_OF": "同事", "COLLABORATED_WITH": "合作伙伴"}
                    rel_types = f.get('rel_types', [])
                    results.append({
                        "name": f_name,
                        "id": str(f.get('id', '')),
                        "rel_types": rel_types,
                        "rel_labels": [rel_map.get(r, r) for r in rel_types],
                        "common_keywords": list(common),
                        "score": len(common)
                    })
            except:
                continue
        
        results.sort(key=lambda x: x['score'], reverse=True)
        if not results:
            return {'found': False, 'recommendations': [], 'message': '在社交圈中未发现技术关键词重合的专家'}
        
        return {
            'found': True,
            'recommendations': results[:top_n],
            'total_found': len(results),
            'message': f'找到 {len(results)} 位技术相关的专家，返回前 {min(top_n, len(results))} 位'
        }
    
    def _path_to_natural_language_from_neo4j_path(self, path):
        """将 Neo4j 路径对象转化为自然语言描述"""
        if not path:
            return ""
        nodes = list(path.nodes)
        if len(nodes) < 2:
            return ""
        
        node_info = []
        for node in nodes:
            try:
                name = node['name']
            except:
                try:
                    name = dict(node).get('name', '')
                except:
                    name = getattr(node, 'name', '') if hasattr(node, 'name') else ''
            node_info.append({'name': name or '未知实体', 'type': list(node.labels)[0] if list(node.labels) else 'Unknown'})
        
        if len(node_info) == 3:
            source_name = node_info[0]['name']
            middle_name = node_info[1]['name']
            target_name = node_info[2]['name']
            if node_info[1]['type'] == 'Patent':
                return f"{source_name}和{target_name}共同拥有专利{middle_name}"
            elif node_info[1]['type'] == 'Organization':
                return f"{source_name}和{target_name}同属于组织{middle_name}"
            else:
                return f"{source_name}通过{node_info[1]['type']}{middle_name}与{target_name}关联"
        elif len(node_info) > 3:
            parts = []
            rel_info = [rel.type for rel in path.relationships]
            for i in range(len(node_info) - 1):
                current_name = node_info[i]['name']
                next_name = node_info[i + 1]['name']
                if i < len(rel_info):
                    rel_label = {'INVENTED': '拥有专利', 'BELONGS_TO': '属于组织'}.get(rel_info[i], rel_info[i])
                    parts.append(f"{current_name}通过{rel_label}关联到{next_name}")
            return f"{node_info[0]['name']}和{node_info[-1]['name']}通过以下路径关联：" + "；".join(parts)
        elif len(node_info) == 2:
            source_name = node_info[0]['name']
            target_name = node_info[1]['name']
            if path.relationships:
                rel_type = path.relationships[0].type
                rel_label = {'COLLABORATED_WITH': '合作', 'IS_COLLEAGUE_OF': '同事关系'}.get(rel_type, rel_type)
                return f"{source_name}和{target_name}存在{rel_label}"
            return f"{source_name}和{target_name}存在关联"
        return "路径描述待实现"
    
    def call(self, params: str, **kwargs) -> str:
        """执行知识图谱检索，并将路径转化为自然语言"""
        params_dict = json5.loads(params)
        source_entity = params_dict.get('source_entity', '').strip()
        target_entity = params_dict.get('target_entity', '').strip()
        relation_type = params_dict.get('relation_type', '').strip()
        max_path_length = params_dict.get('max_path_length', 10)
        
        if not source_entity:
            return json5.dumps({
                'success': False,
                'message': '源实体不能为空',
                'source_entity': source_entity,
                'target_entity': target_entity
            }, ensure_ascii=False)
        
        result = {}
        if target_entity:
            path_result = self.find_path(source_entity, target_entity, max_path_length)
            result = {
                'success': path_result['found'],
                'query_type': 'path',
                'source_entity': source_entity,
                'target_entity': target_entity,
                'path_found': path_result['found'],
                'path_string': path_result.get('path_string'),
                'path_data': path_result.get('path'),
                'natural_language': path_result.get('natural_language'),
                'message': path_result.get('natural_language', path_result.get('message', ''))
            }
        elif relation_type:
            rel_map = {'coauthor': 'coauthor', 'colleague': 'colleague', 'partners': 'coauthor', 'colleagues': 'colleague'}
            mapped_rel_type = rel_map.get(relation_type.lower(), relation_type.lower())
            social_result = self.find_social(source_entity, mapped_rel_type)
            result = {
                'success': social_result['found'],
                'query_type': 'social',
                'source_entity': source_entity,
                'relation_type': relation_type,
                'neighbors': social_result.get('neighbors', []),
                'count': social_result.get('count', 0),
                'message': social_result.get('message', '')
            }
        else:
            recommend_result = self.recommend_similar_experts(source_entity, top_n=5)
            result = {
                'success': recommend_result['found'],
                'query_type': 'recommend',
                'source_entity': source_entity,
                'recommendations': recommend_result.get('recommendations', []),
                'total_found': recommend_result.get('total_found', 0),
                'message': recommend_result.get('message', '')
            }
        
        return json5.dumps(result, ensure_ascii=False)

from neo4j import GraphDatabase
from knowledge_graph.kg_build.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EXPERT_DIR, ORG_DIR, PATENT_DIR
from kg_utils import DataExtractor

class KnowledgeGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.extractor = DataExtractor(EXPERT_DIR, ORG_DIR, PATENT_DIR)

    def close(self):
        self.driver.close()

    def build(self):
        org_map = self.extractor.build_org_map()
        
        with self.driver.session() as session:
            # 1. 自动清空旧数据（实现一键重构）
            print("正在清空旧数据...")
            session.run("MATCH (n) DETACH DELETE n")

            # 2. 创建唯一性约束
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Expert) REQUIRE e.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Patent) REQUIRE p.id IS UNIQUE")

            # 3. 注入组织节点 (仅 ID 和 Name)
            print("正在注入组织节点...")
            for org in self.extractor.get_organizations():
                session.run("MERGE (o:Organization {id: $id}) SET o.name = $name", 
                            id=org['id'], name=org['title'])

            # 4. 注入专利节点 (仅 ID 和 Name)
            print("正在注入专利节点...")
            for patent in self.extractor.get_patents():
                session.run("MERGE (p:Patent {id: $id}) SET p.name = $name", 
                            id=patent['id'], name=patent['title'])

            # 5. 注入专家节点及所有关系
            print("正在注入专家及关系...")
            for exp in self.extractor.get_experts():
                # 创建专家
                session.run("MERGE (e:Expert {id: $id}) SET e.name = $name", 
                            id=exp['id'], name=exp['title'])

                # 建立 [BELONGS_TO] (专家-组织)
                for org_name in exp.get('orgs', []):
                    org_id = org_map.get(org_name)
                    if org_id:
                        session.run("""
                            MATCH (e:Expert {id: $eid}), (o:Organization {id: $oid})
                            MERGE (e)-[:BELONGS_TO]->(o)
                        """, eid=exp['id'], oid=org_id)

                # 建立 [INVENTED] (专家-专利)
                patent_info = exp.get('invent_patents', {})
                for p_item in patent_info.get('patent_list', []):
                    session.run("""
                        MATCH (e:Expert {id: $eid})
                        MERGE (p:Patent {id: $pid})
                        ON CREATE SET p.name = $pname
                        MERGE (e)-[:INVENTED]->(p)
                    """, eid=exp['id'], pid=p_item['id'], pname=p_item.get('title'))

            # 6. 计算生成的社交关系
            print("正在计算合作者与同事关系...")
            # 同一专利即为合作者
            session.run("""
                MATCH (e1:Expert)-[:INVENTED]->(p:Patent)<-[:INVENTED]-(e2:Expert)
                WHERE e1.id < e2.id
                MERGE (e1)-[:COLLABORATED_WITH]-(e2)
            """)
            # 同一组织即为同事
            session.run("""
                MATCH (e1:Expert)-[:BELONGS_TO]->(o:Organization)<-[:BELONGS_TO]-(e2:Expert)
                WHERE e1.id < e2.id
                MERGE (e1)-[:IS_COLLEAGUE_OF]-(e2)
            """)

        print("知识图谱构建完成！")

if __name__ == "__main__":
    builder = KnowledgeGraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        builder.build()
    finally:
        builder.close()
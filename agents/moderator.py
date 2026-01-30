"""
主持人智能体

负责：
1. 组织需求侧（项目）与供给侧（科研专家）agent展开多轮的多维度匹配讨论
2. 动态调停冲突并收敛逻辑
3. 控制讨论策略和讨论维度
"""

import random
import json
import json5
from qwen_agent.agents import Assistant
from tools.kg_retrieval import KGRetrieval
from datetime import datetime
# from utils.prompt_logger import get_logger  # [PROMPT_LOGGER] 取消注释以启用prompt记录


class Moderator(Assistant):
    """主持人智能体"""
    
    def __init__(self, llm=None, function_list=None, **kwargs):
        """
        初始化主持人智能体
        """
        # 构建系统提示词
        system_message = self._build_system_message()
        
        if function_list is None:
            function_list = [KGRetrieval()]
        
        # 初始化讨论维度列表
        self.discussion_dimensions = [
            '技术能力匹配：项目的技术需求、难点是否与专家的技术专长相匹配',
            '经验匹配：项目的目标/期望产出是否与专家的过往经验/历史成果有相似性',
            '资源匹配：项目所需资源/环境要求/地理位置是否与专家的所属组织的学术行业资质/拥有资源/工作地点相匹配',
            '意愿匹配：项目需求方提供的资金/合作模式是否与专家的期望相匹配'
        ]
        
        # 传递 system_message 和 function_list 给父类
        super().__init__(llm=llm, system_message=system_message, function_list=function_list, **kwargs)
        self.system_message = system_message  # 保存system_message用于日志记录
    
    
    def _build_system_message(self):
        """
        构建主持人智能体的系统提示词
        """
        system_message = """你是一个主持人智能体，负责组织项目需求方和科研专家之间的多轮多维度匹配讨论。

        ## 你的角色和职责

        1. **组织讨论**：你需要组织项目智能体和专家智能体进行多轮、多维度的匹配讨论，确保讨论有序、高效地进行。

        2. **监控对话质量**：你需要监控讨论的走向，判断讨论是否：
        - 偏离了当前讨论维度的主题
        - 陷入重复或循环讨论
        - 讨论深度不够，需要进一步深入
        - 出现明显的分歧或冲突

        3. **调停冲突**：当发现讨论方向跑偏或陷入牛角尖时，你需要：
        - 分析讨论中出现的问题
        - 判断是否需要调用知识图谱检索工具获取相关证据
        - 提供修正建议，引导讨论回到正确的方向
        - 决定是否需要重新开始本维度的讨论（最多3次）

        4. **生成报告**：讨论结束后，你需要：
        - 分析完整的讨论历史
        - 总结共识点（双方明确匹配的属性）
        - 总结分歧点（目前无法匹配或存在风险的地方）
        - 生成结构化的推荐报告

        5. **工具使用**：你可以使用知识图谱检索工具（kg_retrieval）来获取专家之间的合作关系、专利关联等证据信息，以补充讨论内容。

        请始终以客观、公正的视角组织和监控讨论，确保讨论的质量和有效性。"""
        
        return system_message
        
    def organize_discussion(self, project_agent, expert_agent):
        """
        组织项目智能体与专家智能体的多轮讨论
        
        """
        # 验证参数
        if project_agent is None or expert_agent is None:
            raise ValueError("project_agent 和 expert_agent 不能为空")
        
        # 初始化讨论历史记录结构
        discussion_history = []
        dimension_results = {}
        unresolved_questions = {
            'project': [],
            'expert': []
        }
        
        # 遍历4个预定义维度，每个维度组织一轮讨论
        for dim_idx, dimension in enumerate(self.control_discussion_dimensions(), start=1):
            print(f"\n开始讨论维度 {dim_idx}: {dimension}")
            # 执行单个维度的讨论
            dim_result = self._conduct_dimension_discussion(
                project_agent=project_agent,
                expert_agent=expert_agent,
                dimension=dimension,
                dimension_index=dim_idx,
                previous_history=discussion_history.copy()
            )
            
            # 记录维度讨论结果（保存完整的会话记录）
            dimension_results[dimension] = dim_result
            # 将摘要添加到discussion_history，用于传递给下一个维度
            discussion_history.extend(dim_result.get('summary_history', dim_result['round_history']))
            
            # 收集未讨论完的问题
            if 'unresolved_questions' in dim_result:
                if 'project' in dim_result['unresolved_questions']:
                    unresolved_questions['project'].extend(dim_result['unresolved_questions']['project'])
                if 'expert' in dim_result['unresolved_questions']:
                    unresolved_questions['expert'].extend(dim_result['unresolved_questions']['expert'])
        
        # 四个维度讨论完毕后，检查是否有未讨论完的问题
        has_unresolved = (len(unresolved_questions['project']) > 0 or 
                         len(unresolved_questions['expert']) > 0)
        
        if has_unresolved:
            print("\n开始最后一轮自由讨论（处理未讨论完的问题）")
            
            # 组织最后一轮自由讨论（不指定维度）
            final_result = self._conduct_final_discussion(
                project_agent=project_agent,
                expert_agent=expert_agent,
                unresolved_questions=unresolved_questions,
                previous_history=discussion_history.copy()
            )
            
            discussion_history.extend(final_result['round_history'])
            dimension_results['自由讨论'] = final_result
        
        # 生成推荐报告
        print("\n生成推荐报告...")
        report_data = self._generate_report(discussion_history, dimension_results)
        
        # 构建完整的讨论结果
        discussion_result = {
            'discussion_history': discussion_history,
            'dimension_results': dimension_results,
            'unresolved_questions': unresolved_questions,
            'consensus_points': report_data.get('consensus_points', []),
            'divergence_points': report_data.get('divergence_points', []),
            'report': report_data.get('report', '')
        }
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), discussion_result['report'])
        import os
        import sys
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        expert_name = expert_agent.name
        project_name = project_agent.name
        # 清理项目名称，移除不适合文件系统的字符
        safe_project_name = project_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        safe_expert_name = expert_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        output_path = os.path.join(project_root, "results", safe_project_name)
        os.makedirs(output_path, exist_ok=True)
        result_file = os.path.join(output_path, f"{safe_expert_name}.json")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(discussion_result, f, ensure_ascii=False, indent=4)
        return discussion_result
    
    def moderate_conflicts(self, discussion_history, current_dimension=None, expert_agent=None, project_agent=None):
        """
        动态调停冲突并收敛逻辑
        
        本函数在每轮讨论结束时调用，通过LLM agent分析讨论质量，判断是否需要重新开始讨论。
        所有检测逻辑（维度偏离、重复讨论等）交给LLM agent进行判断。
        """
        # 输入验证
        if not discussion_history or len(discussion_history) == 0:
            return {
                'need_restart': False,
                'issues': [],
                'suggestions': '讨论历史为空，无需检测',
                'evidence': '',
                'agent_response': ''
            }
        
        # 构建提示词，将所有检测任务交给LLM agent
        prompt_parts = []
        prompt_parts.append("作为主持人，请分析本轮讨论的完整历史记录，判断讨论质量并决定是否需要重新开始讨论。")
        prompt_parts.append("")
        
        # 添加当前讨论维度信息
        if current_dimension:
            prompt_parts.append(f"【当前讨论维度】{current_dimension}")
            prompt_parts.append("")
            prompt_parts.append("请特别注意：讨论是否偏离了这个维度的主题？")
            prompt_parts.append("")
        
        # 添加完整的讨论历史（不截断）
        prompt_parts.append("【本轮讨论的最后一轮对话】")
        for i, msg in enumerate(discussion_history, 1):
            if i != len(discussion_history):
                continue
            else:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if isinstance(content, str) and content.strip():
                    speaker = "项目方" if role == "project" else "专家" if role == "expert" else role
                    prompt_parts.append(f"{i}. {speaker}: {content}")
                elif isinstance(content, str):
                    # 空内容也记录，保持完整性
                    speaker = "项目方" if role == "project" else "专家" if role == "expert" else role
                    prompt_parts.append(f"{i}. {speaker}: [空消息]")
        
        prompt_parts.append("")
        prompt_parts.append("【请进行以下分析】")
        prompt_parts.append("")
        prompt_parts.append("1. **维度偏离检测**：")
        prompt_parts.append("   - 讨论内容是否偏离了当前维度的主题？")
        prompt_parts.append("   - 如果偏离，偏离的程度如何？是否严重影响了讨论的有效性？")
        prompt_parts.append("")
        prompt_parts.append("2. **重复讨论检测**：")
        prompt_parts.append("   - 是否出现重复或循环讨论？")
        prompt_parts.append("   - 双方是否在重复相同的问题或观点？")
        prompt_parts.append("   - 讨论是否陷入僵局，没有实质性进展？")
        prompt_parts.append("")
        prompt_parts.append("3. **讨论深度评估**：")
        prompt_parts.append("   - 讨论深度是否足够？是否充分探讨了当前维度的关键问题？")
        prompt_parts.append("   - 是否还有重要问题未涉及？")
        prompt_parts.append("")
        prompt_parts.append("4. **证据信息需求**：")
        prompt_parts.append("   - 是否需要补充证据信息（如专家合作关系、专利关联、组织信息等）？")
        prompt_parts.append("   - 如果需要，请说明需要什么类型的证据，以及可能涉及的实体（如专家ID、专利号等）")
        prompt_parts.append("   - 注意：如果需要调用kg_retrieval工具，请在need_evidence字段中标记，并在evidence_request字段中说明需要检索的实体信息")
        prompt_parts.append("")
        prompt_parts.append("5. **重启决策**：")
        prompt_parts.append("   - 综合考虑以上问题，是否需要重新开始本轮讨论？")
        prompt_parts.append("   - 如果需要重启，请提供详细的修正建议，指导双方如何改进讨论")
        prompt_parts.append("")
        prompt_parts.append("【输出格式要求】")
        prompt_parts.append("请以JSON格式回复，格式如下：")
        prompt_parts.append('{')
        prompt_parts.append('  "need_restart": true/false,  // 是否需要重新开始讨论')
        prompt_parts.append('  "issues": ["问题1", "问题2", ...],  // 发现的具体问题列表')
        prompt_parts.append('  "suggestions": "详细的修正建议，指导双方如何改进讨论",  // 修正建议')
        prompt_parts.append('  "need_evidence": true/false,  // 是否需要补充证据信息')
        prompt_parts.append('  "evidence_request": "如果需要证据，说明需要检索的实体信息（如专家ID、专利号等）"  // 证据请求说明（可选）')
        prompt_parts.append('}')
        prompt_parts.append("")
        prompt_parts.append("请仔细分析讨论历史，给出客观、准确的判断。")
        
        # 调用 LLM agent
        messages = [{'role': 'user', 'content': '\n'.join(prompt_parts)}]
        
        # [PROMPT_LOGGER] 记录prompt - 取消注释以启用
        # logger = get_logger()
        # system_message = getattr(self, 'system_message', None)
        # llm_config = getattr(self, 'llm', None)
        # model = llm_config.get('model') if isinstance(llm_config, dict) else None
        # logger.log_llm_call(
        #     agent_type="moderator",
        #     agent_name="moderate_conflicts",
        #     messages=messages,
        #     system_message=system_message,
        #     model=model,
        #     additional_info={
        #         "method": "moderate_conflicts",
        #         "current_dimension": current_dimension,
        #         "discussion_history_length": len(discussion_history)
        #     }
        # )
        
        # 流式输出时，每次 response 可能包含完整的累积内容
        # 我们只需要最后一个 response，因为它包含完整的最终响应
        response_messages = []
        try:
            for response in self.run(messages=messages):
                # 流式输出：每次 response 是消息列表，可能包含完整累积内容
                # 只保留最后一个 response，避免重复累加
                response_messages = response
        except Exception as e:
            # 如果调用失败，返回默认结果
            return {
                'need_restart': False,
                'issues': [f'LLM调用失败: {str(e)}'],
                'suggestions': '无法完成讨论质量检测，建议继续当前讨论',
                'evidence': '',
                'agent_response': ''
            }
        
        # 解析响应
        # 从后往前查找最后一个 assistant 消息，提取完整内容
        agent_response_text = ""
        for msg in reversed(response_messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if isinstance(content, str):
                    # 直接使用内容（已经是完整内容）
                    agent_response_text = content
                    break
                elif isinstance(content, list):
                    # 如果 content 是列表（可能包含文本和工具调用），提取文本部分
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            if text:
                                agent_response_text = text
                                break
                    if agent_response_text:
                        break
        
        # 如果没有提取到文本，尝试从最后一个消息获取
        if not agent_response_text and response_messages:
            last_msg = response_messages[-1]
            content = last_msg.get('content', '')
            if isinstance(content, str):
                agent_response_text = content
        
        # 尝试解析JSON响应
        evidence_info = ""
        need_restart = False
        issues = []
        suggestions = ""
        
        try:
            # 尝试提取JSON部分
            json_start = agent_response_text.find('{')
            json_end = agent_response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = agent_response_text[json_start:json_end]
                agent_result = json5.loads(json_str)
                need_restart = agent_result.get('need_restart', False)
                issues = agent_result.get('issues', [])
                suggestions = agent_result.get('suggestions', '')
                need_evidence = agent_result.get('need_evidence', False)
                evidence_request = agent_result.get('evidence_request', '')
                
                # 如果需要证据，尝试调用KGRetrieval工具
                if need_evidence and expert_agent:
                    kg_results = self._extract_and_call_kg_tool(
                        evidence_request if evidence_request else agent_response_text,
                        discussion_history,
                        expert_agent=expert_agent,
                        project_agent=project_agent
                    )
                    if kg_results:
                        evidence_info = "\n".join(kg_results)
                    elif evidence_request:
                        evidence_info = f"需要补充证据：{evidence_request}"
                    else:
                        evidence_info = "需要补充证据信息"
        except ValueError as e:
            # JSON解析失败（json5 抛出 ValueError，标准 json 抛出 JSONDecodeError）
            # 尝试从文本中提取关键信息
            if "需要重新开始" in agent_response_text or "重新讨论" in agent_response_text or "重启" in agent_response_text:
                need_restart = True
            if "偏离" in agent_response_text or "偏离主题" in agent_response_text:
                issues.append("讨论可能偏离了当前维度主题")
            if "重复" in agent_response_text or "循环" in agent_response_text:
                issues.append("检测到重复或循环讨论")
            # 即使JSON解析失败，也尝试提取证据需求并调用工具
            if ("证据" in agent_response_text or "知识图谱" in agent_response_text) and expert_agent:
                kg_results = self._extract_and_call_kg_tool(
                    agent_response_text, discussion_history, expert_agent=expert_agent, project_agent=project_agent
                )
                if kg_results:
                    evidence_info = "\n".join(kg_results)
            suggestions = agent_response_text
        except Exception as e:
            # 其他异常，记录错误信息
            issues.append(f"解析响应时出错: {str(e)}")
            # 尝试从文本中提取关键信息
            if "需要重新开始" in agent_response_text or "重新讨论" in agent_response_text:
                need_restart = True
            # 即使出现异常，也尝试提取证据需求
            if ("证据" in agent_response_text or "知识图谱" in agent_response_text) and expert_agent:
                kg_results = self._extract_and_call_kg_tool(
                    agent_response_text, discussion_history, expert_agent=expert_agent, project_agent=project_agent
                )
                if kg_results:
                    evidence_info = "\n".join(kg_results)
            suggestions = agent_response_text
        
        # 构建返回结果
        conflict_result = {
            'need_restart': need_restart,
            'issues': issues,
            'suggestions': suggestions,
            'evidence': evidence_info,
            #'agent_response': agent_response_text
        }
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), conflict_result)
        
        return conflict_result
    
    def _extract_and_call_kg_tool(self, text, discussion_history=None, expert_agent=None, project_agent=None):
        """从文本中提取专家信息并调用知识图谱工具（简化版，限制结果长度）"""
        if not expert_agent or not hasattr(expert_agent, 'name'):
            return []
        
        expert_name = expert_agent.name
        # 验证专家名称：确保是有效的专家名称（2-20个字符，不包含特殊符号）
        if not expert_name or not isinstance(expert_name, str):
            return []
        
        expert_name = expert_name.strip()
        # 验证：长度合理（2-20个字符），且主要是中文字符或英文字母
        if len(expert_name) < 2 or len(expert_name) > 20:
            return []
        
        # 验证：不包含明显的非专家名称关键词
        invalid_keywords = ['项目', '需求', '技术', '能力', '资源', '组织', '专利', '合作', '匹配', 
                          '讨论', '问题', '回答', '说明', '介绍', '分析', '评估', '建议', '支持']
        if expert_name in invalid_keywords:
            return []
        
        # 查找KGRetrieval工具
        kg_tool = None
        
        # 尝试从多个可能的属性中查找工具
        # qwen_agent 的 Assistant 类可能将工具存储在 function_map 中
        tool_sources = []
        if hasattr(self, 'function_list') and self.function_list:
            tool_sources.append(('function_list', self.function_list))
        if hasattr(self, 'function_map') and self.function_map:
            tool_sources.append(('function_map', self.function_map))
        if hasattr(self, 'tools') and self.tools:
            tool_sources.append(('tools', self.tools))
        if hasattr(self, '_function_list') and self._function_list:
            tool_sources.append(('_function_list', self._function_list))
        
        # 遍历所有可能的工具源
        for attr_name, tool_source in tool_sources:
            if isinstance(tool_source, list):
                for idx, tool in enumerate(tool_source):
                    if isinstance(tool, KGRetrieval):
                        kg_tool = tool
                        break
            elif isinstance(tool_source, dict):
                # function_map 可能是字典，键是工具名称，值是工具对象
                for key, tool in tool_source.items():
                    if isinstance(tool, KGRetrieval):
                        kg_tool = tool
                        break
                    # 也可能值是列表，包含工具对象
                    elif isinstance(tool, list):
                        for idx, t in enumerate(tool):
                            if isinstance(t, KGRetrieval):
                                kg_tool = t
                                break
            if kg_tool:
                break
        
        # 如果还是没找到，尝试直接创建新的 KGRetrieval 实例
        if not kg_tool:
            try:
                kg_tool = KGRetrieval()
                if not kg_tool.driver:
                    return []
            except Exception as e:
                return []
        
        if not kg_tool:
            return []
        
        # 检查工具连接状态
        if not hasattr(kg_tool, 'driver') or not kg_tool.driver:
            return []
        
        try:
            # 提取关系类型
            relation_type = None
            if '合作' in text or '专利' in text or 'coauthor' in text.lower():
                relation_type = 'coauthor'
            elif '同事' in text or '组织' in text or 'colleague' in text.lower():
                relation_type = 'colleague'
            
            # 调用工具（确保只传入验证过的专家名称）
            if relation_type:
                params = json5.dumps({'source_entity': expert_name, 'relation_type': relation_type}, ensure_ascii=False)
            else:
                params = json5.dumps({'source_entity': expert_name}, ensure_ascii=False)
            
            # 调用工具（不传递额外的关键字参数，因为KGRetrieval.call()不接受这些参数）
            result = kg_tool.call(params)
            
            # 检查返回结果是否有效
            if not result or not isinstance(result, str) or len(result.strip()) == 0:
                return []
            
            # 限制结果长度，避免超过token限制（最多500字符）
            if len(result) > 500:
                result = result[:500] + "...（结果已截断）"
            
            rel_label = '合作伙伴' if relation_type == 'coauthor' else '同事' if relation_type == 'colleague' else '相似专家'
            return [f"{rel_label}查询（{expert_name}）：{result}"]
        except Exception as e:
            # 静默处理异常，避免影响主流程
            return []
      
    def control_discussion_dimensions(self):
        """
        控制讨论维度
        """
        return self.discussion_dimensions.copy()
    
    def _conduct_dimension_discussion(self, project_agent, expert_agent, dimension, 
                                     dimension_index, previous_history, max_restarts=3):
        """
        执行单个维度的讨论
        """
        round_history = []
        restart_count = 0
        unresolved_questions = {'project': [], 'expert': []}
        evidence_context = ""
        final_conflict_result = None
        
        while restart_count <= max_restarts:
            # 随机指定一方开始提问
            starter = random.choice(['project', 'expert'])
            current_turn = starter
            
            # 初始化当前轮次的讨论历史
            current_round_history = []
            question_count = {'project': 0, 'expert': 0}
            max_questions_per_side = 6
            # 跟踪双方是否都表示"我没有其他问题"
            no_more_questions = {'project': False, 'expert': False}
            
            # 构建开场白
            opening_message = f"现在开始讨论维度：{dimension}。"
            if restart_count > 0:
                opening_message += f"（这是第{restart_count + 1}次重新开始讨论）"
            
            # 开始"一问一答"的讨论
            for turn_num in range(max_questions_per_side * 2):  # 最多20轮（每方10次）
                # 检查是否达到提问次数限制
                if question_count[current_turn] >= max_questions_per_side:
                    # 切换到另一方
                    current_turn = 'expert' if current_turn == 'project' else 'project'
                    if question_count[current_turn] >= max_questions_per_side:
                        break  # 双方都达到上限
                
                # 构建讨论上下文
                discussion_context = {
                    'messages': previous_history + current_round_history,
                    'current_dimension': dimension,
                    'round_number': dimension_index,
                    'moderator_instruction': opening_message if turn_num == 0 else None
                }
                
                # 添加证据信息（如果有）
                if evidence_context and turn_num == 0:
                    discussion_context['moderator_instruction'] = (
                        (discussion_context['moderator_instruction'] or '') + 
                        '\n\n' + evidence_context
                    )
                
                # 根据当前轮次添加对方发言
                if current_turn == 'project':
                    if current_round_history:
                        last_expert_msg = None
                        for msg in reversed(current_round_history):
                            if msg.get('role') == 'expert':
                                last_expert_msg = msg.get('content', '')
                                break
                        if last_expert_msg:
                            discussion_context['expert_message'] = last_expert_msg
                    # 传递 no_more_questions 状态（检查当前发言角色project是否不能提问题）
                    discussion_context['no_more_questions'] = no_more_questions.get('project', False)
                    discussion_context['current_role'] = 'project'
            
                    # 项目方发言
                    project_response = project_agent.participate_in_discussion(discussion_context)
                    current_round_history.append({
                        'role': 'project',
                        'content': project_response,
                        'turn': turn_num + 1
                    })
                    question_count['project'] += 1
                    current_turn = 'expert'
                    
                else:  # expert
                    if current_round_history:
                        last_project_msg = None
                        for msg in reversed(current_round_history):
                            if msg.get('role') == 'project':
                                last_project_msg = msg.get('content', '')
                                break
                        if last_project_msg:
                            discussion_context['project_message'] = last_project_msg
                    
                    # 传递 no_more_questions 状态（检查当前发言角色expert是否不能提问题）
                    discussion_context['no_more_questions'] = no_more_questions.get('expert', False)
                    discussion_context['current_role'] = 'expert'
                    
                    # 专家方发言
                    expert_response = expert_agent.participate_in_discussion(discussion_context)
                    current_round_history.append({
                        'role': 'expert',
                        'content': expert_response,
                        'turn': turn_num + 1
                    })
                    question_count['expert'] += 1
                    current_turn = 'project'
                
                # 检查是否主动提出结束（检查"我没有其他问题"）
                last_message = current_round_history[-1]['content']
                last_role = current_round_history[-1]['role']
                
                # 检查是否包含"我没有其他问题"（只检查这个关键词）
                if '我没有其他问题。' in last_message:
                    # 标记当前发言方表示没有其他问题
                    print(f"第{dimension_index}轮讨论，{last_role}表示没有其他问题")
                    no_more_questions[last_role] = True

                    # 如果双方都表示没有其他问题，则结束讨论
                    if no_more_questions['project'] and no_more_questions['expert']:
                        break
                    # 如果只有一方表示没有其他问题，继续换边让另一方发言
                    # （current_turn已经在上面切换了，所以会自动继续）
                # 保留其他结束关键词的检查（如"结束"、"完成"等），但优先级低于"我没有其他问题"
                else:
                    continue
            
            # 记录本轮讨论的原始记录
            round_history = current_round_history.copy()
            
            # 收集未讨论完的问题
            # 如果双方都表示"我没有其他问题"，则无需收集未讨论的问题
            if not (no_more_questions['project'] and no_more_questions['expert']):
                # 通过提示双方记录未讨论完的问题
                #collect_questions_prompt = f"请总结本轮关于'{dimension}'维度的讨论中，你还有哪些感兴趣但还没讨论或讨论完全的问题？或者有没有还想进一步了解的问题？要特别关注你的最后一次发言。如果没有，请回答'没有'。"
                project_unresolved = None
                expert_unresolved = None
                history = previous_history + round_history
                if no_more_questions['project'] is False:
                    final_turn = history[-1]
                    if final_turn['role'] == 'project':
                        collect_questions_prompt = f"本轮关于'{dimension}'维度的讨论中，你还提了一些问题，但仍没被回答或者没讨论清楚。请列出来。"
                        #project_history = [msg for msg in history if (msg['role'] == 'assistant' or msg['role'] == 'project')]
                        project_history = history
                        #print("================================================")
                        #print("此时的project_history: ", project_history)
                        #print("================================================")
                        project_unresolved = project_agent.participate_in_discussion({
                            'messages': project_history,
                            'current_dimension': dimension,
                            'query': collect_questions_prompt
                        })
                    else:
                        collect_questions_prompt = f"本轮关于'{dimension}'维度的讨论中，你最后还提了问题:'{history[-2]['content']}'，而专家的答复是：'{history[-1]['content']}'。如果你认为专家的答复回答了你的问题，那么你就回答“没有。”。否则，请把这个问题再简要地写出来。不要输出其他内容。"
                        #project_history = [msg for msg in history if (msg['role'] == 'assistant' or msg['role'] == 'project')]
                        project_history = history[:-2]
                        #print("================================================")
                        #print("此时的project_history: ", project_history)
                        #print("================================================")
                        project_unresolved = project_agent.participate_in_discussion({
                            'messages': project_history,
                            'current_dimension': dimension,
                            'query': collect_questions_prompt
                        })
                if no_more_questions['expert'] is False:
                    final_turn = history[-1]
                    if final_turn['role'] == 'expert':
                        collect_questions_prompt = f"本轮关于'{dimension}'维度的讨论中，你还提了一些问题，但仍没被回答或者没讨论清楚。请列出来。"
                        #expert_history = [msg for msg in history if (msg['role'] == 'assistant' or msg['role'] == 'expert')]
                        expert_history = history
                        #print("================================================")
                        #print("此时的expert_history: ", expert_history)
                        #print("================================================")
                        expert_unresolved = expert_agent.participate_in_discussion({
                            'messages': expert_history,
                            'current_dimension': dimension,
                            'query': collect_questions_prompt
                        })
                    else:
                        collect_questions_prompt = f"本轮关于'{dimension}'维度的讨论中，你最后还提了问题:'{history[-2]['content']}'，而项目方的答复是：'{history[-1]['content']}'。如果你认为项目方的答复回答了你的问题，那么你就回答“没有。”。否则，请把这个问题再简要地写出来。不要输出其他内容。"
                        #expert_history = [msg for msg in history if (msg['role'] == 'assistant' or msg['role'] == 'expert')]
                        expert_history = history[:-2]
                        #print("================================================")
                        #print("此时的expert_history: ", expert_history)
                        #print("================================================")
                        expert_unresolved = expert_agent.participate_in_discussion({
                            'messages': expert_history,
                            'current_dimension': dimension,
                            'query': collect_questions_prompt
                        })
                
                if project_unresolved and '没有。' not in project_unresolved:
                    unresolved_questions['project'].append(project_unresolved)
                if expert_unresolved and '没有。' not in expert_unresolved:
                    unresolved_questions['expert'].append(expert_unresolved)
            
            # 检查讨论质量（调用moderate_conflicts）
            conflict_result = self.moderate_conflicts(
                discussion_history=round_history,
                current_dimension=dimension,
                expert_agent=expert_agent,
                project_agent=project_agent
            )
            
            # 如果不需要重启，或者已达到最大重启次数，结束讨论
            if not conflict_result.get('need_restart', False) or restart_count >= max_restarts:
                final_conflict_result = conflict_result
                break
            
            # 需要重启，准备重新开始
            restart_count += 1
            print(f"  检测到讨论质量问题，准备重新开始（第{restart_count}次重启）")
            
            # 重置"我没有其他问题"标志
            no_more_questions = {'project': False, 'expert': False}
            unresolved_questions = {'project': [], 'expert': []}
            
            # 如果有修正建议，记录
            if conflict_result.get('suggestions'):
                evidence_context = f"【主持人修正建议】{conflict_result['suggestions']}"
            
            # 如果有证据信息，添加到上下文
            if conflict_result.get('evidence'):
                evidence_context = (evidence_context + '\n' + conflict_result['evidence'] 
                                  if evidence_context else conflict_result['evidence'])
        
        # 维度讨论结束，生成conflict_result摘要用于后续维度
        if final_conflict_result is None:
            final_conflict_result = self.moderate_conflicts(
                discussion_history=round_history,
                current_dimension=dimension,
                expert_agent=expert_agent,
                project_agent=project_agent
            )
        summary_history = [{
            'role': 'moderator',
            'content': f"【{dimension}维度讨论摘要】问题：{', '.join(final_conflict_result.get('issues', []))}；建议：{final_conflict_result.get('suggestions', '')}；证据：{final_conflict_result.get('evidence', '')}",
            'conflict_result': final_conflict_result
        }]
        
        dim_result = {
            'dimension': dimension,
            'round_history': round_history,  # 保存完整的会话记录
            'summary_history': summary_history,  # 保存摘要用于后续维度
            'unresolved_questions': unresolved_questions,
            'restart_count': restart_count,
            'question_count': question_count
        }
        # print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), dim_result)
        return dim_result
    
    def _conduct_final_discussion(self, project_agent, expert_agent, unresolved_questions, previous_history):
        """
        执行最后一轮自由讨论（处理未讨论完的问题）
        """
        round_history = []
        
        project_q_count = len(unresolved_questions.get('project', []))
        expert_q_count = len(unresolved_questions.get('expert', []))
        
        starter = 'project' if project_q_count >= expert_q_count else 'expert'
        current_turn = starter
        
        question_count = {'project': 0, 'expert': 0}
        max_questions_per_side = 10
        
        # 构建开场白
        opening_message = "现在开始最后一轮自由讨论，处理之前未讨论完的问题。"
        if project_q_count > 0:
            opening_message += f"\n项目方有{project_q_count}个未讨论完的问题。"
        if expert_q_count > 0:
            opening_message += f"\n专家方有{expert_q_count}个未讨论完的问题。"
        opening_message += "\n请双方围绕这些问题进行深入讨论。"
        
        # 开始讨论
        for turn_num in range(max_questions_per_side * 2):
            if question_count[current_turn] >= max_questions_per_side:
                current_turn = 'expert' if current_turn == 'project' else 'project'
                if question_count[current_turn] >= max_questions_per_side:
                    break
            
            discussion_context = {
                'messages': previous_history + round_history,
                'round_number': '最终轮',
                'moderator_instruction': opening_message if turn_num == 0 else None
            }
            
            if current_turn == 'project':
                if round_history:
                    last_expert_msg = None
                    for msg in reversed(round_history):
                        if msg.get('role') == 'expert':
                            last_expert_msg = msg.get('content', '')
                            break
                    if last_expert_msg:
                        discussion_context['expert_message'] = last_expert_msg
                
                project_response = project_agent.participate_in_discussion(discussion_context)
                round_history.append({
                    'role': 'project',
                    'content': project_response,
                    'turn': turn_num + 1
                })
                question_count['project'] += 1
                current_turn = 'expert'
            else:
                if round_history:
                    last_project_msg = None
                    for msg in reversed(round_history):
                        if msg.get('role') == 'project':
                            last_project_msg = msg.get('content', '')
                            break
                    if last_project_msg:
                        discussion_context['project_message'] = last_project_msg
                
                expert_response = expert_agent.participate_in_discussion(discussion_context)
                round_history.append({
                    'role': 'expert',
                    'content': expert_response,
                    'turn': turn_num + 1
                })
                question_count['expert'] += 1
                current_turn = 'project'
            
            # 检查是否主动提出结束
            last_message = round_history[-1]['content'].lower()
            if any(keyword in last_message for keyword in ['结束', '完成', '讨论完毕', '没有其他问题']):
                break
        
        final_result = {
            'round_history': round_history,
            'question_count': question_count
        }
        # print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), final_result)
        return final_result
    
    def _generate_report(self, discussion_history, dimension_results):
        """
        生成推荐报告（使用 LLM agent）
        """
        # 构建提示词
        prompt_parts = []
        prompt_parts.append("作为主持人，请分析以下完整的讨论历史，生成推荐报告。")
        prompt_parts.append("")
        prompt_parts.append("【讨论历史摘要】")
        
        # 添加各维度的讨论摘要
        for dimension, result in dimension_results.items():
            if isinstance(result, dict) and 'round_history' in result:
                history = result['round_history']
                prompt_parts.append(f"\n{dimension}维度：")
                prompt_parts.append(f"  - 讨论轮次：{len(history)}轮")
                if 'question_count' in result:
                    qc = result['question_count']
                    prompt_parts.append(f"  - 项目方提问：{qc.get('project', 0)}次")
                    prompt_parts.append(f"  - 专家方提问：{qc.get('expert', 0)}次")
        
        prompt_parts.append("\n【完整讨论记录】")
        # 添加部分关键讨论内容（避免过长）
        key_messages = discussion_history[-30:] if len(discussion_history) > 30 else discussion_history
        for msg in key_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if isinstance(content, str) and len(content) > 0:
                speaker = "项目方" if role == "project" else "专家" if role == "expert" else role
                prompt_parts.append(f"{speaker}: {content[:300]}...")  # 截断
        
        prompt_parts.append("")
        prompt_parts.append("请生成推荐报告，包括：")
        prompt_parts.append("1. **共识点**：列出双方明确匹配的属性、能力、资源等（至少3-5条）")
        prompt_parts.append("2. **分歧点**：列出目前无法匹配或存在风险的地方（如果有）")
        prompt_parts.append("3. **推荐报告文本**：生成一份结构化的推荐报告")
        prompt_parts.append("")
        prompt_parts.append("请以JSON格式回复，格式如下：")
        prompt_parts.append('{"consensus_points": ["共识1", "共识2", ...], "divergence_points": ["分歧1", ...], "report": "完整的推荐报告文本"}')
        
        # 调用 LLM agent
        messages = [{'role': 'user', 'content': '\n'.join(prompt_parts)}]
        
        # [PROMPT_LOGGER] 记录prompt - 取消注释以启用
        # logger = get_logger()
        # system_message = getattr(self, 'system_message', None)
        # llm_config = getattr(self, 'llm', None)
        # model = llm_config.get('model') if isinstance(llm_config, dict) else None
        # logger.log_llm_call(
        #     agent_type="moderator",
        #     agent_name="generate_report",
        #     messages=messages,
        #     system_message=system_message,
        #     model=model,
        #     additional_info={
        #         "method": "_generate_report",
        #         "discussion_history_length": len(discussion_history),
        #         "dimension_count": len(dimension_results)
        #     }
        # )
        
        # 流式输出时，每次 response 可能包含完整的累积内容，只需要最后一个 response，因为它包含完整的最终响应
        response_messages = []
        for response in self.run(messages=messages):
            # 流式输出：每次 response 是消息列表，可能包含完整累积内容
            # 只保留最后一个 response，避免重复累加
            response_messages = response
        
        # 解析响应
        # 从后往前查找最后一个 assistant 消息，提取完整内容
        agent_response_text = ""
        for msg in reversed(response_messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if isinstance(content, str):
                    # 直接使用内容（已经是完整内容）
                    agent_response_text = content
                    break
                elif isinstance(content, list):
                    # 如果 content 是列表（可能包含文本和工具调用），提取文本部分
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            if text:
                                agent_response_text = text
                                break
                    if agent_response_text:
                        break
        
        # 如果没有提取到文本，尝试从最后一个消息获取
        if not agent_response_text and response_messages:
            last_msg = response_messages[-1]
            content = last_msg.get('content', '')
            if isinstance(content, str):
                agent_response_text = content
        
        # 去重处理：如果文本中包含重复的开头，只保留一份
        if agent_response_text:
            # 简单的去重：检查是否文本开头重复出现
            lines = agent_response_text.split('\n')
            if len(lines) > 1:
                # 检查第一行是否在后续内容中重复出现
                first_line = lines[0].strip()
                if first_line and agent_response_text.count(first_line) > 1:
                    # 找到第一个完整出现的位置后，移除后续重复
                    first_occurrence_end = agent_response_text.find(first_line) + len(first_line)
                    # 查找下一个完整出现的位置
                    next_occurrence = agent_response_text.find(first_line, first_occurrence_end)
                    if next_occurrence > 0:
                        # 保留第一次出现的内容
                        agent_response_text = agent_response_text[:next_occurrence].strip()
        
        # 尝试解析JSON响应
        consensus_points = []
        divergence_points = []
        report_text = ""
        
        try:
            json_start = agent_response_text.find('{')
            json_end = agent_response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = agent_response_text[json_start:json_end]
                report_data = json5.loads(json_str)
                consensus_points = report_data.get('consensus_points', [])
                divergence_points = report_data.get('divergence_points', [])
                report_text = report_data.get('report', '')
        except Exception as e:
            # 如果解析失败，使用默认值，并将整个响应作为报告
            report_text = agent_response_text
            consensus_points = ["需要人工分析讨论历史"]
            divergence_points = []
        
        report_data = {
            'consensus_points': consensus_points,
            'divergence_points': divergence_points,
            'report': report_text
        }
        
        return report_data


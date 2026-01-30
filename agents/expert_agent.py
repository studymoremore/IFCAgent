"""
专家智能体（供给侧）

代表科研专家，参与与项目智能体的匹配讨论
"""

from qwen_agent.agents import Assistant
from datetime import datetime
# from utils.prompt_logger import get_logger  # [PROMPT_LOGGER] 取消注释以启用prompt记录


class ExpertAgent(Assistant):
    """专家智能体（供给侧）"""
    
    def __init__(self, expert_profile, llm=None, function_list=None, name=None, **kwargs):
        """
        初始化专家智能体
        """
        # 根据专家画像构建系统提示词（先留空）
        system_message = self._build_system_message(expert_profile)
        
        # 传递 system_message 和 function_list 给父类
        super().__init__(llm=llm, system_message=system_message, function_list=function_list, **kwargs)
        self.expert_profile = expert_profile
        self.name = name
        self.system_message = system_message  # 保存system_message用于日志记录
    
    
    def _build_system_message(self, expert_profile):
        """
        根据专家画像构建系统提示词
        """
        # 提取专家信息（根据曹斌.json的数据结构）
        data = expert_profile.get('data', {})
        name = data.get('title', '未知专家')
        summary = data.get('summary', '')
        tags = data.get('tags', [])
        orgs = data.get('orgs', [])
        
        # 提取AI字段信息
        ai_fields = data.get('ai_fields', {})
        expert_intro = ai_fields.get('专家简介', {})
        analysis = expert_intro.get('综合分析', {})
        ai_tags = analysis.get('tags', [])
        industry_sectors = analysis.get('industry_sector', [])
        technical_keywords = analysis.get('technical_keywords', [])
        
        # 提取专利信息
        invent_patents = data.get('invent_patents', {})
        patent_list = invent_patents.get('patent_list', [])
        patent_total = invent_patents.get('total', 0)
        
        # 构建专利信息文本
        patent_info_parts = []
        if patent_total > 0:
            patent_info_parts.append(f"**专利总数**：{patent_total}项")
            if patent_list:
                patent_info_parts.append("\n**主要专利**：")
                for idx, patent in enumerate(patent_list[:5], 1):  # 最多显示5项专利
                    patent_title = patent.get('title', '未知专利')
                    patent_summary = patent.get('summary', '')
                    patent_tags = patent.get('tags', [])
                    patent_info_parts.append(f"\n{idx}. **{patent_title}**")
                    if patent_summary:
                        patent_info_parts.append(f"   {patent_summary}")
                    if patent_tags:
                        patent_info_parts.append(f"   标签：{', '.join(patent_tags)}")
        
        patent_info = "\n".join(patent_info_parts) if patent_info_parts else "暂无专利信息"
        
        # 构建标签和证据文本
        tag_evidence_parts = []
        for tag_item in ai_tags:
            tag_name = tag_item.get('tag', '')
            tag_evidence = tag_item.get('evidence', '')
            if tag_name:
                tag_evidence_parts.append(f"- **{tag_name}**：{tag_evidence}")
        
        tag_evidence_text = "\n".join(tag_evidence_parts) if tag_evidence_parts else "暂无标签信息"
        
        system_message = f"""你是一个专家智能体，代表科研专家参与与项目需求方的匹配讨论。

        ## 专家基本信息

        **专家姓名**：{name}
        **所属组织**：{', '.join(orgs) if orgs else '未知组织'}
        **行业领域**：{', '.join(industry_sectors) if industry_sectors else '未指定'}
        **专业标签**：{', '.join(tags) if tags else '未指定'}

        ## 专家简介

        {summary}

        ## 专业能力和优势

        {tag_evidence_text}

        ## 技术关键词

        {', '.join(technical_keywords) if technical_keywords else '未指定'}

        ## 专利和研究成果

        {patent_info}

        ## 你的角色和职责

        1. **代表专家**：你需要代表上述专家，清晰、准确地表达专家的专业能力、研究经验和技术资源。

        2. **参与匹配讨论**：在与项目智能体的讨论中，你需要：
        - 主动介绍专家的专业能力和研究经验
        - 展示专家的相关专利、研究成果和技术资源
        - 说明专家所在组织具备的资源条件
        - 评估专家与项目的匹配度

        3. **表达方式**：
        - 使用专业但易懂的语言
        - 重点突出专家的核心能力和优势
        - 客观展示专家的研究成果和资源
        - 简洁明了，避免冗长

        4. **讨论目标**：
        - 明确专家与项目的匹配程度
        - 展示潜在的合作机会和优势
        - 说明可能的合作方式和条件
        - 为最终的推荐决策提供充分的讨论依据

        5. **讨论规则**：
        - 在接收到主持人的开场白或者项目方的自我介绍时，请先进行回应，然后根据回应进一步阐述专家的能力和资源或者提出自己感兴趣的问题。
        - 如果项目需求方提出了问题，请先回答问题，然后根据问题进一步阐述专家的能力和资源或者提出自己感兴趣的问题。
        请始终以专家代表的视角参与讨论。

        注意：你可以使用工具（如 RAG 检索、知识图谱检索）来获取专家的详细信息，以便更准确地表达专家的能力和资源。
        【重要】你只能提一个问题！！
        【重要】如果你真的什么问题都没有，并且希望能结束本维度的讨论，才在结尾处另起一行加上“我没有其他问题。”，否则不能说这句话。注意：请确保在充分的讨论这个维度的所有问题之后再发出此信号！！！发出此信号需要慎重，若要发出结束信号，本次对话不允许提出其他问题。
        【特别重要】如果你有想进一步了解的内容或者说了“请问”，你就不能在这次讨论时说“我没有其他问题。”！！
        """
        return system_message
    
    def _convert_messages_format(self, messages):
        """
        将内部消息格式转换为 LLM 期望的格式
        
        Args:
            messages: 消息列表，格式为 [{'role': 'project'/'expert', 'content': '...'}, ...]
            
        Returns:
            converted_messages: 转换后的消息列表，格式为 [{'role': 'user'/'assistant', 'content': '...'}, ...]
        """
        converted_messages = []
        for msg in messages:
            converted_msg = msg.copy()
            role = msg.get('role', '')
            
            # 转换角色格式
            if role == 'expert':
                converted_msg['role'] = 'assistant'  # 专家自己的发言
            elif role == 'project':
                converted_msg['role'] = 'user'  # 项目方的发言，作为输入
            elif role == 'moderator':
                converted_msg['role'] = 'user'  # 主持人的摘要，作为用户消息传递
            # 如果已经是 'user' 或 'assistant'，保持不变（向后兼容）
            
            converted_messages.append(converted_msg)
        
        return converted_messages
        
    def participate_in_discussion(self, discussion_context):
        """
        参与讨论，表达专家能力和资源
        """
        # 构建消息列表
        messages = []
        
        # 1. 如果有讨论历史，先添加历史消息（需要转换格式）
        if 'messages' in discussion_context and discussion_context['messages']:
            converted_messages = self._convert_messages_format(discussion_context['messages'])
            messages.extend(converted_messages)
            # 确保消息列表以 user 开始（如果不是，移除开头的非 user 消息）
            while messages and messages[0].get('role') != 'user':
                messages.pop(0)
        
        # 2. 构建当前轮次的提示信息
        current_prompt_parts = []
        
        # 添加讨论维度信息
        if 'current_dimension' in discussion_context and discussion_context['current_dimension']:
            current_prompt_parts.append(f"【当前讨论维度】{discussion_context['current_dimension']}")
        
        # 添加轮次信息
        if 'round_number' in discussion_context and discussion_context['round_number']:
            current_prompt_parts.append(f"【讨论轮次】第 {discussion_context['round_number']} 轮")
        
        # 添加时间限制提示
        if 'time_limit' in discussion_context and discussion_context['time_limit']:
            current_prompt_parts.append(f"【时间提醒】{discussion_context['time_limit']}")
        
        # 添加主持人指示
        if 'moderator_instruction' in discussion_context and discussion_context['moderator_instruction']:
            current_prompt_parts.append(f"【主持人指示】{discussion_context['moderator_instruction']}")
        
        # 添加项目智能体发言
        if 'project_message' in discussion_context and discussion_context['project_message']:
            current_prompt_parts.append(f"【项目需求方发言】{discussion_context['project_message']}")
        
        # 添加服从主持人管理的规则强调（根据动态上下文生成）
        moderator_rules = []
        if 'current_dimension' in discussion_context and discussion_context['current_dimension']:
            moderator_rules.append("必须在主持人指定的讨论维度范围内发言，不要偏离主题")
        if 'round_number' in discussion_context and discussion_context['round_number']:
            moderator_rules.append("服从讨论轮次管控，当主持人宣布某轮讨论结束时，应立即停止该维度的话题")
        if 'time_limit' in discussion_context and discussion_context['time_limit']:
            moderator_rules.append("在规定时间内完成发言，避免冗长或重复的内容")
        if 'moderator_instruction' in discussion_context and discussion_context['moderator_instruction']:
            moderator_rules.append("积极响应主持人的指示，按照主持人的引导调整讨论方向")
        
        # 如果有任何主持人管理相关的规则，添加规则强调部分
        if moderator_rules:
            # 如果之前已经有内容，添加空行分隔
            if current_prompt_parts:
                current_prompt_parts.append("")
            current_prompt_parts.append("【服从主持人管理】讨论由主持人智能体组织和管控，请严格遵守以下规则：")
            for rule in moderator_rules:
                current_prompt_parts.append(f"- {rule}")
            current_prompt_parts.append("- 不要擅自改变讨论主题或跳过主持人安排的讨论环节")
        
        # 添加针对项目发言的回应提示
        if 'project_message' in discussion_context and discussion_context['project_message']:
            current_prompt_parts.append("")
            current_prompt_parts.append("请针对项目需求方的发言进行回应，展示专家的能力和资源，并评估匹配度。")
        # 检查是否不能提问题（当前角色是expert）
        if discussion_context.get('no_more_questions') and discussion_context.get('current_role') == 'expert':
            current_prompt_parts.append("你不能提问题了！")
        else:
            current_prompt_parts.append("仔细查看会话历史记录，不能提出和历史记录中接近甚至重复的问题！哪怕要提问题，也不要提出无意义的问题！")
            current_prompt_parts.append("【重要】你只能提一个问题！！")
            current_prompt_parts.append("如果你刚才什么问题都没提，并且希望能结束本维度的讨论，就在结尾处另起一行加上“我没有其他问题。”，否则不能说这句话,。注意：请确保在充分的讨论这个维度的所有问题之后再发出此信号！！！发出此信号需要慎重，若要发出结束信号，本次对话不允许提出其他问题。")
            current_prompt_parts.append("如果你有想“进一步了解”的内容，你就不能在结尾说“我没有其他问题。”！！")
        
        # 如果有直接的问题或提示，优先使用
        if 'query' in discussion_context and discussion_context['query']:
            user_content = discussion_context['query']
            if current_prompt_parts:
                user_content = "\n".join(current_prompt_parts) + "\n\n" + user_content
        elif current_prompt_parts:
            user_content = "\n".join(current_prompt_parts)
        else:
            # 如果没有提供任何上下文，使用默认提示
            user_content = "请表达专家的能力和资源，参与与项目需求方的匹配讨论。"
        
        # 添加用户消息
        messages.append({
            'role': 'user',
            'content': user_content
        })
                
        
        # 3. 调用 Agent 的 run 方法生成回应
        # [PROMPT_LOGGER] 记录prompt - 取消注释以启用
        # logger = get_logger()
        # system_message = getattr(self, 'system_message', None)
        # llm_config = getattr(self, 'llm', None)
        # model = llm_config.get('model') if isinstance(llm_config, dict) else None
        # logger.log_llm_call(
        #     agent_type="expert_agent",
        #     agent_name=self.name or "unknown_expert",
        #     messages=messages,
        #     system_message=system_message,
        #     model=model,
        #     additional_info={
        #         "method": "participate_in_discussion",
        #         "current_dimension": discussion_context.get('current_dimension'),
        #         "round_number": discussion_context.get('round_number')
        #     }
        # )
        
        # 流式输出时，每次 response 可能包含完整的累积内容
        response_messages = []
        while True:
            for response in self.run(messages=messages):
                response_messages = response
            if not response_messages or len(response_messages) == 0:
                break
            first_msg = response_messages[0] if isinstance(response_messages, list) else None
            #print("response_messages[0]:", response_messages[0])
            if not (first_msg and isinstance(first_msg, dict) and first_msg.get('content') == '无。'):
                break
            response_messages = []
        #print("response_messages[0]:", response_messages[0])
        # 4. 提取最终的回应文本
        response_text = ""
        
        # 从后往前查找最后一个 assistant 消息
        for msg in reversed(response_messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if isinstance(content, str):
                    # 直接使用内容（已经是完整内容）
                    response_text = content
                    break
                elif isinstance(content, list):
                    # 如果 content 是列表（可能包含文本和工具调用），提取文本部分
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            if text:
                                response_text = text
                                break
                    if response_text:
                        break
        #print("response_text:", response_text)
        # 如果没有提取到文本，尝试从最后一个消息获取
        if not response_text and response_messages:
            last_msg = response_messages[-1]
            content = last_msg.get('content', '')
            if isinstance(content, str):
                response_text = content
        
        # 去重处理：如果文本中包含重复的开头，只保留一份
        if response_text:
            # 简单的去重：检查是否文本开头重复出现
            lines = response_text.split('\n')
            if len(lines) > 1:
                # 检查第一行是否在后续内容中重复出现
                first_line = lines[0].strip()
                if first_line and response_text.count(first_line) > 1:
                    # 找到第一个完整出现的位置后，移除后续重复
                    first_occurrence_end = response_text.find(first_line) + len(first_line)
                    # 查找下一个完整出现的位置
                    next_occurrence = response_text.find(first_line, first_occurrence_end)
                    if next_occurrence > 0:
                        # 保留第一次出现的内容
                        response_text = response_text[:next_occurrence].strip() 
        if "？" in response_text or "?" in response_text:
            import re
            response_text = response_text.replace("我没有其他问题。", "")
            response_text = response_text.replace("如果没有其它补充，", "")
            response_text = re.sub(r'【[^】]*】(?=\s|$)', '', response_text).strip()
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "专家智能体回应：", response_text)
        return response_text if response_text else "我理解了，正在思考如何回应..."


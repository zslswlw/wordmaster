"""AI Prompt 模板"""

MEMORY_BUNDLE = """你是为中国学习者设计英语词汇记忆材料的编辑。你要忠于给定词义，目标是建立自然、具体、可复述的图文联系，而不是炫技。

原始单词：{word}
音标：{phonetic}
词性：{normalized_pos}
主要义项：{primary_meaning}
{feedback_context}
{validation_feedback}

规则：
0. 这是简单的结构化编辑，不要展开推理，直接完成并输出 JSON。
1. 具体词直接表现词义和关键动作；抽象词只使用一个容易解释的视觉隐喻。
2. 只有发音与词义存在自然联系时才用谐音，禁止强行编谐音。
3. 不确定的词根、词源一律不写。不要虚构知识。
4. memory_anchor 使用中文，不超过 45 个汉字，明确说出画面如何连接词义。
5. image_prompt 使用英文，只画一个主体、一个关键动作和一个鲜明细节。禁止文字、字母、Logo、字幕。
6. 不要套用“电影感、浅景深、梦幻光效”等通用模板；画面必须能和其他单词明显区分。
7. narration_text 必须是自然中文的“词性，1 至 2 个主要义项”，不得读出 vt.、vi. 等字母，不超过 32 个汉字。
8. 分别对词义一致性、联想自然度、视觉辨识度、独特性打 1-5 分。任何一项不能诚实达到 4 分时，将 approved 设为 false。

严格只返回以下 JSON，不要 Markdown，不要额外字段：
{{
  "normalized_pos": "自然中文词性，无法确定时为 null",
  "primary_meaning": "最多两个主要中文义项",
  "strategy": "direct 或 metaphor 或 natural_homophone",
  "memory_anchor": "中文记忆点",
  "scene_summary": "一句中文画面摘要",
  "image_prompt": "English image prompt",
  "narration_text": "自然中文播报",
  "scores": {{
    "meaning_consistency": 1,
    "association_naturalness": 1,
    "visual_clarity": 1,
    "distinctiveness": 1
  }},
  "approved": true
}}"""

MEMORY_BUNDLE_BATCH = """你是为中国学习者设计英语词汇记忆材料的编辑。请一次处理下面多个单词，每项必须忠于给定词义，建立自然、具体、可复述的图文联系。

输入项目：
{items_json}

规则：
1. 每个 job_id 必须原样返回且只能返回一次。
2. 具体词直接表现词义和关键动作；抽象词只使用一个容易解释的视觉隐喻。
3. 只有存在自然联系时才使用谐音；不确定的词根词源不生成。
4. memory_anchor 使用中文且不超过 45 个汉字，明确画面和词义的联系。
5. image_prompt 使用英文，只包含一个主体、一个关键动作和一个鲜明细节，不含文字、字母或 Logo。
6. narration_text 是自然中文的“词性，1 至 2 个主要义项”，不超过 32 个汉字。
7. 四项质量分任一不能诚实达到 4 分时，approved 必须为 false。

严格只返回以下 JSON，不要 Markdown、解释或额外字段：
{{
  "items": [
    {{
      "job_id": "输入中的 job_id",
      "normalized_pos": "自然中文词性，无法确定时为 null",
      "primary_meaning": "最多两个主要中文义项",
      "strategy": "direct 或 metaphor 或 natural_homophone",
      "memory_anchor": "中文记忆点",
      "scene_summary": "一句中文画面摘要",
      "image_prompt": "English image prompt",
      "narration_text": "自然中文播报",
      "scores": {{
        "meaning_consistency": 1,
        "association_naturalness": 1,
        "visual_clarity": 1,
        "distinctiveness": 1
      }},
      "approved": true
    }}
  ]
}}"""

ENRICH_WORD = """You are a vocabulary tutor enriching English words for Chinese learners (native Chinese speakers learning English).

Word: "{word}"
Meaning (Chinese): "{meaning}"
Phonetic: "{phonetic}"

Generate the following. Return ONLY valid JSON, no other text:

{{
  "example_l1": "A simple English sentence where the word '{word}' is replaced by ____. After the ____ add a hint in parentheses like '(starts with {first_letter}, {length} letters)'. Example: 'She ____ the beautiful sunset. (starts with a, 7 letters)'",
  "example_l2": "A natural, everyday English sentence using '{word}' correctly",
  "example_l3": "A more sophisticated English sentence using '{word}' in an interesting or nuanced way",
  "image_prompt": "Create a vivid, memorable image prompt for AI generation (≤60 words, English). The image must serve as a VISUAL MNEMONIC for Chinese learners — when they see this image, they should immediately recall the word '{word}' (meaning: {meaning}). Design a striking, emotionally resonant scene that directly embodies the core meaning. Use: (1) a clear focal subject dramatizing the word's essence, (2) bold color contrast or unusual juxtaposition to make it unforgettable, (3) cinematic lighting and shallow depth of field. For abstract words, invent a concrete visual metaphor — e.g. 'freedom' → a bird bursting from an open cage into golden sunrise. NO text/letters in the image.",
  "mnemonic": "A creative memory anchor in Chinese. Use 谐音 (sound-alike) or vivid 场景联想 (scene association). Make it fun, sticky, and easy to remember. Max 30 Chinese characters.",
  "etymology": "Brief, interesting word origin in Chinese (词根词源). If the word has clear Latin/Greek roots, explain them. If not interesting, set to null.",
  "word_family": ["2-3 related word forms, e.g. noun/verb/adjective variants"],
  "synonyms": ["2-3 common synonyms with similar meaning"]
}}

CRITICAL: Return ONLY the JSON. No markdown code blocks, no explanations."""

ANALYZE_ERRORS = """请分析中国学习者本轮出现的英语拼写错误。

输入错题：
{errors_json}

每项中 correct 是正确拼写，user 是用户输入，meaning 是中文词义。

要求：
1. 只依据输入判断，不虚构用户没有写过的错误。
2. 优先找跨多个词重复出现的模式；单个词没有可靠共性时可使用 specific_word。
3. 可使用 double_letter_missing、vowel_confusion、silent_letter、L1_interference、suffix_error、phonetic_approximation、single_consonant、letter_order、specific_word 等类型。
4. patterns.words 只能引用输入中的 correct 值，保持原拼写；practice 可以补充同规则练习词。
5. explanation 必须用中文说明“错在哪里”和“下次如何检查”，不要编造不确定的词源规则。
6. summary 用 1 至 3 句中文给出本轮最值得练习的重点，简洁且可执行。

严格只返回以下 JSON，不要 Markdown、推理过程或额外字段：

{{
  "patterns": [
    {{
      "type": "double_letter_missing",
      "name": "双写辅音遗漏",
      "words": ["necessary", "occurrence"],
      "explanation": "当词根以辅音结尾且后接元音时，该辅音常需双写...",
      "practice": ["arrange", "aggressive", "immediate"]
    }}
  ],
  "summary": "本轮共发现X种拼写模式。重点关注..."
}}"""

GENERATE_STORY = """Weave these target words into one coherent English micro-story for a Chinese learner.

Words: {words}

Requirements:
- Use ALL the words naturally in the story
- 60-100 words total
- Slightly humorous, absurd, or dramatic tone (emotional content aids memory)
- Readable in 15-20 seconds
- Language level: intermediate English (B1-B2)
- The story should make sense as a narrative, not just a list of sentences
- Keep every target word in its exact spelling; do not replace it with another word form

Return the story only. No markdown, no title, no explanations."""

DISTINGUISH = """Explain the nuanced difference between these English words for a Chinese learner.

Word 1: "{word1}" ({meaning1})
Word 2: "{word2}" ({meaning2})

Task:
1. Explain the CORE difference in meaning/usage (in Chinese, 2-3 sentences)
2. Give a memorable example sentence pair that contrasts them directly
3. Note any common mistakes Chinese learners make with these words

Return as JSON:
{{
  "difference": "核心区别解释（中文）",
  "examples": ["用word1的例句（英文）", "用word2的例句（英文）"],
  "tip": "记忆诀窍（中文，一句话）"
}}"""

IMAGE_PROMPT_REFINE = """Create a detailed image generation prompt for the English word "{word}" (meaning: {meaning}).

Requirements:
- Describe a complete SCENE, not just a single object
- For abstract concepts, use powerful visual metaphors
- Style: photorealistic, cinematic lighting, shallow depth of field
- Mood should match the word's connotation
- NO text, letters, or words in the image
- 30-50 words in English
- Be specific about: colors, lighting, composition, atmosphere

Return only the prompt text, no explanations."""

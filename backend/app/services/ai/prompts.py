"""AI Prompt 模板"""

ENRICH_WORD = """You are a vocabulary tutor enriching English words for Chinese learners (native Chinese speakers learning English).

Word: "{word}"
Meaning (Chinese): "{meaning}"
Phonetic: "{phonetic}"

Generate the following. Return ONLY valid JSON, no other text:

{{
  "example_l1": "A simple English sentence where the word '{word}' is replaced by ____. After the ____ add a hint in parentheses like '(starts with {first_letter}, {length} letters)'. Example: 'She ____ the beautiful sunset. (starts with a, 7 letters)'",
  "example_l2": "A natural, everyday English sentence using '{word}' correctly",
  "example_l3": "A more sophisticated English sentence using '{word}' in an interesting or nuanced way",
  "image_prompt": "A detailed English prompt for AI image generation (≤50 words). Describe a photorealistic, cinematic scene that VISUALLY captures the essence of '{word}'. For abstract concepts, use powerful visual metaphors. Focus on mood, lighting, composition. NO text in the image.",
  "mnemonic": "A creative memory anchor in Chinese. Use 谐音 (sound-alike) or vivid 场景联想 (scene association). Make it fun, sticky, and easy to remember. Max 30 Chinese characters.",
  "etymology": "Brief, interesting word origin in Chinese (词根词源). If the word has clear Latin/Greek roots, explain them. If not interesting, set to null.",
  "word_family": ["2-3 related word forms, e.g. noun/verb/adjective variants"],
  "synonyms": ["2-3 common synonyms with similar meaning"]
}}

CRITICAL: Return ONLY the JSON. No markdown code blocks, no explanations."""

ANALYZE_ERRORS = """Analyze these English spelling errors from a native Chinese speaker learning English.

Errors:
{errors_json}

For each error, the format is: {{"word": "correct_spelling", "user": "what_user_typed", "meaning": "Chinese meaning"}}

Task:
1. Identify common ERROR PATTERNS across multiple words:
   - double_letter_missing: user missed a double consonant (e.g. "necessary" → "necesary")
   - vowel_confusion: wrong vowel (e.g. "separate" → "seperate", ie/ei confusion)
   - silent_letter: missed a silent letter (e.g. "government" → "goverment")
   - L1_interference: Chinese pronunciation influenced the spelling
   - suffix_error: wrong word ending (-tion/-sion, -able/-ible, -ence/-ance)
   - phonetic_approximation: user spelled phonetically but incorrectly
   - single_consonant: doubled a letter that should be single

2. Group the errors by pattern. Each pattern should list the words that exhibit it.

3. For each pattern, provide:
   - A clear explanation of the rule (in Chinese)
   - Suggested practice words that reinforce the same rule

4. Give a brief, encouraging summary.

Respond in Chinese. Keep it concise and actionable. Format as JSON:

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

GENERATE_STORY = """Weave these English words into a coherent micro-story.

Words: {words}

Requirements:
- Use ALL the words naturally in the story
- 60-100 words total
- Slightly humorous, absurd, or dramatic tone (emotional content aids memory)
- Readable in 15-20 seconds
- Language level: intermediate English (B1-B2)
- The story should make sense as a narrative, not just a list of sentences

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

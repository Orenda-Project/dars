# Intelligent Chapter Planner — Diagnostic Report
_Generated locally via the Agents SDK backend (real LLM) on the current module (post D-15: `recommended_lp_type` not sent to the LLM)._
_Backend: `AgentSdkPlannerLLM` (Claude Code session). 2 chapters, full pipeline captured: inputs → system+user prompt → raw response → parsed plan → validator → coverage._

## Executive summary

| Chapter | Periods | LLM latency | Raw JSON valid? | Validator | Topic cov | Sub-SLO cov |
|---|---|---|---|---|---|---|
| Ch.1 Hello, World | 6 | 22.1s | ❌ (prose preamble before JSON) | n/a — parse failed | — | — |
| Ch.2 My Family | 7 | 18.3s | ✅ | **PASS ✅** | 3/3 | 5/5 |

**Plan quality (where it parsed): strong.** Ch.2 produced a pedagogically sound plan — mixed lp_types (`comprehension_word_meanings`, `reading`, `grammar`, `creative_writing` — chosen purely from topic text + statements per D-15, no recommendation fed), two formative assessments placed after teaching blocks, full topic and sub-SLO coverage. Ch.1's *content* was also good (it even merged the two greeting topics and split "Letters A–E" into a reading then a grammar lesson) — it only failed on output **format**.

**The one real failure mode: output framing, not reasoning.** Ch.1 returned valid JSON **preceded by a prose sentence** ("Looking at the topics, I'll sequence..."). The parser strips ```` ``` ```` fences but not leading prose, so `json.loads` fails at char 0. The model's *plan* was fine; it just narrated first.
- This is intermittent (~1 in 2 here; varies per call). Under **D-16 (no fallback, no retry)** this becomes a hard, user-facing `/plan` failure — the teacher would see the break-down fail and have to re-trigger.
- Cheap mitigations exist but are explicitly **out of scope per D-16** (no retry) and would otherwise be: (a) extract the first `{...}` JSON object from the response instead of requiring it at char 0; (b) strengthen the prompt's "no prose" instruction; (c) prefill the assistant turn with `{`.

**Latency:** 18–22s per chapter (single non-streaming-equivalent call via the SDK). Acceptable for an on-demand "break it down", but worth noting it's a multi-second blocking call.

**Takeaway:** the planning *intelligence* is working as designed (good lp_type variety, sensible FA placement, merges/splits, full coverage). The risk to address before this is reliable in production is **response-framing robustness** — currently the dominant failure cause, made fatal by the no-fallback decision.


# Chapter 1: Hello, World — 6 periods

_Chapter 1 — Hello, World_


## 1. Inputs (topics + SLOs + sub-SLOs)

- Subject: `Eng` · Period count: **6** · Topics: **4**
- Chapter SLOs: R1-01, V1-01, W1-01, G1-04


### Topic Greetings
- sub-SLOs: `V1-01-a`, `G1-04-b`, `W1-04-b`

```text
Hello, friends! Welcome to your first English book.
When we meet someone, we say 'hello'. We can also say 'good morning' in the morning.
We say 'good afternoon' when the sun is high. We say 'good night' before we sleep.

Here are some greetings to learn:
  Hello.
  Good morning.
  Good afternoon.
  Good night.

When someone says hello to you, you say hello back. This is being polite.
Now look at your friend. Say 'Hello!' to your friend. Your friend will say 'Hello!' back.
```

### Topic My Name Is
- sub-SLOs: `G1-04-b`, `W1-03-a`, `V1-01-a`

```text
When we meet a new person, they may ask, 'What is your name?'
We tell them our name. We use the words 'My name is …'.

Here is Ali. Ali says, 'My name is Ali.'
Here is Ayesha. Ayesha says, 'My name is Ayesha.'
Here is Hassan. Hassan says, 'My name is Hassan.'

Now it is your turn. Stand up. Say to the class:
  My name is _______.
Put your own name in the blank. This is how we tell people who we are.
```

### Topic Letters A to E
- sub-SLOs: `R1-01-a`, `R1-01-b`, `R1-01-d`, `W1-01-a`, `W1-01-b`

```text
The English alphabet has 26 letters. Today we will learn the first five.

  A a   like in 'apple'
  B b   like in 'ball'
  C c   like in 'cat'
  D d   like in 'dog'
  E e   like in 'egg'

Each letter has two forms. The big form is called uppercase. The small form is called lowercase.
A is the uppercase letter. a is the lowercase letter. They are the same letter, but they look different.

Practice writing each letter five times on your slate.
Start at the top. Move your pencil carefully.
Make the letter as big as the space between the lines.

Now look at these words:
  apple  ball  cat  dog  egg
Each word begins with one of our five letters. Can you point to each letter?
```

### Topic Practice — Say and Write
- sub-SLOs: `R1-01-c`, `W1-01-d`, `G1-04-b`

```text
Now we put it all together.

Practice 1: Match the uppercase letter to its lowercase pair.
  A   b
  B   d
  C   a
  D   e
  E   c

Practice 2: Read each word aloud.
  apple, ball, cat, dog, egg

Practice 3: Say it.
  Hello. My name is _______. I am six years old.

Practice 4: Write your name three times on a clean line of your notebook.
```

## 2. LLM system prompt (verbatim)

```text
You are a curriculum planner. Given a chapter's topics, the sub-SLOs each topic teaches, and a fixed number of teaching periods, produce an ordered plan of exactly N periods. Each period is either a lesson (one LP that may combine several thin topics or focus on part of a dense one) or a formative assessment (FA) that checks sub-SLOs already taught. Sequence lessons before the FAs that assess them. Every topic must be taught by at least one lesson. Choose an lp_type for each lesson only from the allowed list. Cover all the chapter's sub-SLOs across the lessons. Place FAs where they best consolidate learning — you decide how many and where. Output strict JSON only, no prose, no markdown fences. Use only the topic_id and sub_slo_id values supplied; do not invent UUIDs. The JSON shape is:
{"items": [{"kind": "lp", "topic_ids": ["<uuid>"], "lp_type": "<allowed>", "sub_slo_ids": ["<uuid>"]}, {"kind": "fa", "topic_ids": ["<uuid>"], "sub_slo_ids": ["<uuid>"]}]}
```

## 3. LLM user prompt (verbatim JSON payload)

_4855 chars_

```json
{"subject_code": "Eng", "period_count": 6, "allowed_lp_types": ["comprehension_qa", "comprehension_word_meanings", "creative_writing", "grammar", "reading", "revision"], "topics": [{"topic_id": "00506b74-abc3-5ac5-9c52-42aef81fd9c0", "title": "Greetings", "topic_text": "Hello, friends! Welcome to your first English book.\nWhen we meet someone, we say 'hello'. We can also say 'good morning' in the morning.\nWe say 'good afternoon' when the sun is high. We say 'good night' before we sleep.\n\nHere are some greetings to learn:\n  Hello.\n  Good morning.\n  Good afternoon.\n  Good night.\n\nWhen someone says hello to you, you say hello back. This is being polite.\nNow look at your friend. Say 'Hello!' to your friend. Your friend will say 'Hello!' back.", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "c4169334-f4ca-5e65-b812-ad23f56d761c", "code": "V1-01-a", "statement": "Use everyday social/family vocabulary in context."}, {"sub_slo_id": "269d4d3f-f469-5be5-9001-2ade455c6698", "code": "G1-04-b", "statement": "Introduce oneself using 'My name is ___'."}, {"sub_slo_id": "e7b31475-f216-5afd-a40b-62f630f0b218", "code": "W1-04-b", "statement": "Copy short sentences legibly."}]}, {"topic_id": "f5b162fb-ca6b-5715-a613-08c030d482d8", "title": "My Name Is", "topic_text": "When we meet a new person, they may ask, 'What is your name?'\nWe tell them our name. We use the words 'My name is …'.\n\nHere is Ali. Ali says, 'My name is Ali.'\nHere is Ayesha. Ayesha says, 'My name is Ayesha.'\nHere is Hassan. Hassan says, 'My name is Hassan.'\n\nNow it is your turn. Stand up. Say to the class:\n  My name is _______.\nPut your own name in the blank. This is how we tell people who we are.", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "269d4d3f-f469-5be5-9001-2ade455c6698", "code": "G1-04-b", "statement": "Introduce oneself using 'My name is ___'."}, {"sub_slo_id": "eeaf351f-a719-5142-b3e3-35592b8ccd96", "code": "W1-03-a", "statement": "Write own name correctly."}, {"sub_slo_id": "c4169334-f4ca-5e65-b812-ad23f56d761c", "code": "V1-01-a", "statement": "Use everyday social/family vocabulary in context."}]}, {"topic_id": "af9c4682-f0d2-5c50-aeb6-1a901ea8fb42", "title": "Letters A to E", "topic_text": "The English alphabet has 26 letters. Today we will learn the first five.\n\n  A a   like in 'apple'\n  B b   like in 'ball'\n  C c   like in 'cat'\n  D d   like in 'dog'\n  E e   like in 'egg'\n\nEach letter has two forms. The big form is called uppercase. The small form is called lowercase.\nA is the uppercase letter. a is the lowercase letter. They are the same letter, but they look different.\n\nPractice writing each letter five times on your slate.\nStart at the top. Move your pencil carefully.\nMake the letter as big as the space between the lines.\n\nNow look at these words:\n  apple  ball  cat  dog  egg\nEach word begins with one of our five letters. Can you point to each letter?", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "9f75ab04-1851-51c4-881c-5f66fedc2a41", "code": "R1-01-a", "statement": "Recognise uppercase letters A–E."}, {"sub_slo_id": "607c76da-c036-5f39-8290-b8435ed9b5a3", "code": "R1-01-b", "statement": "Recognise lowercase letters a–e."}, {"sub_slo_id": "813b776b-3fc4-5510-ad12-763afae820b5", "code": "R1-01-d", "statement": "Identify the initial sound of A–E words."}, {"sub_slo_id": "f4fd2f34-8a3b-5f79-8aa6-f2ed92ff5efe", "code": "W1-01-a", "statement": "Form uppercase letters A–E."}, {"sub_slo_id": "ef1deff6-c0c5-50aa-8d7e-1da8dad08385", "code": "W1-01-b", "statement": "Form lowercase letters a–e."}]}, {"topic_id": "6cb5b9cf-3982-55c2-8417-13b1052827ef", "title": "Practice — Say and Write", "topic_text": "Now we put it all together.\n\nPractice 1: Match the uppercase letter to its lowercase pair.\n  A   b\n  B   d\n  C   a\n  D   e\n  E   c\n\nPractice 2: Read each word aloud.\n  apple, ball, cat, dog, egg\n\nPractice 3: Say it.\n  Hello. My name is _______. I am six years old.\n\nPractice 4: Write your name three times on a clean line of your notebook.", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "a5752494-921f-5ff9-88ce-5d231ec9786f", "code": "R1-01-c", "statement": "Match uppercase to lowercase letters A–E."}, {"sub_slo_id": "61fd3e7b-516e-5b84-801c-8aef106c0dd6", "code": "W1-01-d", "statement": "Write simple CVC words beginning with A–E."}, {"sub_slo_id": "269d4d3f-f469-5be5-9001-2ade455c6698", "code": "G1-04-b", "statement": "Introduce oneself using 'My name is ___'."}]}], "chapter_slos": [{"code": "R1-01", "statement": "Recognise and form the letters of the alphabet."}, {"code": "V1-01", "statement": "Use basic social-interaction and family vocabulary."}, {"code": "W1-01", "statement": "Form letters and simple words legibly."}, {"code": "G1-04", "statement": "Use simple sentence frames to introduce oneself."}]}
```

## 4. Raw LLM response

_latency: **22.1s** · response length: 1774 chars_

```json
Looking at the topics, I'll sequence lessons before FAs and ensure all topics/sub-SLOs are covered across 6 periods.

{"items": [{"kind": "lp", "topic_ids": ["00506b74-abc3-5ac5-9c52-42aef81fd9c0", "f5b162fb-ca6b-5715-a613-08c030d482d8"], "lp_type": "comprehension_word_meanings", "sub_slo_ids": ["c4169334-f4ca-5e65-b812-ad23f56d761c", "269d4d3f-f469-5be5-9001-2ade455c6698", "eeaf351f-a719-5142-b3e3-35592b8ccd96", "e7b31475-f216-5afd-a40b-62f630f0b218"]}, {"kind": "fa", "topic_ids": ["00506b74-abc3-5ac5-9c52-42aef81fd9c0", "f5b162fb-ca6b-5715-a613-08c030d482d8"], "sub_slo_ids": ["c4169334-f4ca-5e65-b812-ad23f56d761c", "269d4d3f-f469-5be5-9001-2ade455c6698", "eeaf351f-a719-5142-b3e3-35592b8ccd96"]}, {"kind": "lp", "topic_ids": ["af9c4682-f0d2-5c50-aeb6-1a901ea8fb42"], "lp_type": "reading", "sub_slo_ids": ["9f75ab04-1851-51c4-881c-5f66fedc2a41", "607c76da-c036-5f39-8290-b8435ed9b5a3", "813b776b-3fc4-5510-ad12-763afae820b5"]}, {"kind": "lp", "topic_ids": ["af9c4682-f0d2-5c50-aeb6-1a901ea8fb42"], "lp_type": "grammar", "sub_slo_ids": ["f4fd2f34-8a3b-5f79-8aa6-f2ed92ff5efe", "ef1deff6-c0c5-50aa-8d7e-1da8dad08385"]}, {"kind": "lp", "topic_ids": ["6cb5b9cf-3982-55c2-8417-13b1052827ef"], "lp_type": "creative_writing", "sub_slo_ids": ["a5752494-921f-5ff9-88ce-5d231ec9786f", "61fd3e7b-516e-5b84-801c-8aef106c0dd6", "269d4d3f-f469-5be5-9001-2ade455c6698"]}, {"kind": "fa", "topic_ids": ["af9c4682-f0d2-5c50-aeb6-1a901ea8fb42", "6cb5b9cf-3982-55c2-8417-13b1052827ef"], "sub_slo_ids": ["9f75ab04-1851-51c4-881c-5f66fedc2a41", "607c76da-c036-5f39-8290-b8435ed9b5a3", "813b776b-3fc4-5510-ad12-763afae820b5", "f4fd2f34-8a3b-5f79-8aa6-f2ed92ff5efe", "ef1deff6-c0c5-50aa-8d7e-1da8dad08385", "a5752494-921f-5ff9-88ce-5d231ec9786f", "61fd3e7b-516e-5b84-801c-8aef106c0dd6"]}]}
```

## 5. Parsed plan & validator verdict

**LLM path raised:** `PlannerLLMError('failed to parse LLM plan: Expecting value: line 1 column 1 (char 0)')`

> Under D-16 (no fallback) this would fail the /plan request.



# Chapter 2: My Family — 7 periods

_Chapter 2 — My Family_


## 1. Inputs (topics + SLOs + sub-SLOs)

- Subject: `Eng` · Period count: **7** · Topics: **3**
- Chapter SLOs: V1-01, G1-01, W1-04


### Topic People in My Family
- sub-SLOs: `V1-01-a`, `G1-01-a`

```text
A family is a group of people who live together and love each other.
In my family there are many people. Let me tell you about them.

My mother is the woman who takes care of me. I call her 'Ammi' or 'Mama'.
My father is the man who works for our family. I call him 'Abba' or 'Papa'.
My sister is a girl. She is older than me. I call her 'Bajee'.
My brother is a boy. He is younger than me.
My grandmother is my father's mother. I call her 'Dadi'.
My grandfather is my father's father. I call him 'Dada'.

Some families are small. Some families are big. All families are special.
```

### Topic This Is My Family
- sub-SLOs: `W1-04-b`, `V1-01-a`, `G1-01-b`

```text
Look at the picture of Ali's family.
Ali says, 'This is my family. We are six people.'

Ali points to each person:
  This is my mother. Her name is Fatima.
  This is my father. His name is Imran.
  This is my sister. Her name is Ayesha.
  This is my brother. His name is Bilal.
  This is my grandmother. Her name is Zaitun.
  This is my grandfather. His name is Yousuf.

Names are special words. We always write a name with a capital letter at the start.
Look: Fatima. Imran. Ayesha. Each name starts with a big letter.
```

### Topic I Love My Family
- sub-SLOs: `W1-04-b`, `G1-04-b`

```text
I love my family. My family loves me.
I have one mother. I have one father. I have one sister and one brother.
We live in a small house together.

Now write about your own family.
Use these sentence helpers:
  My name is _______.
  My mother's name is _______.
  My father's name is _______.
  I have _______ brothers and _______ sisters.

Read your sentences out loud to a friend.
Listen carefully when your friend reads about their family.
```

## 2. LLM system prompt (verbatim)

```text
You are a curriculum planner. Given a chapter's topics, the sub-SLOs each topic teaches, and a fixed number of teaching periods, produce an ordered plan of exactly N periods. Each period is either a lesson (one LP that may combine several thin topics or focus on part of a dense one) or a formative assessment (FA) that checks sub-SLOs already taught. Sequence lessons before the FAs that assess them. Every topic must be taught by at least one lesson. Choose an lp_type for each lesson only from the allowed list. Cover all the chapter's sub-SLOs across the lessons. Place FAs where they best consolidate learning — you decide how many and where. Output strict JSON only, no prose, no markdown fences. Use only the topic_id and sub_slo_id values supplied; do not invent UUIDs. The JSON shape is:
{"items": [{"kind": "lp", "topic_ids": ["<uuid>"], "lp_type": "<allowed>", "sub_slo_ids": ["<uuid>"]}, {"kind": "fa", "topic_ids": ["<uuid>"], "sub_slo_ids": ["<uuid>"]}]}
```

## 3. LLM user prompt (verbatim JSON payload)

_3359 chars_

```json
{"subject_code": "Eng", "period_count": 7, "allowed_lp_types": ["comprehension_qa", "comprehension_word_meanings", "creative_writing", "grammar", "reading", "revision"], "topics": [{"topic_id": "2c32314a-2c05-526b-baee-a4e7ac9b5a85", "title": "People in My Family", "topic_text": "A family is a group of people who live together and love each other.\nIn my family there are many people. Let me tell you about them.\n\nMy mother is the woman who takes care of me. I call her 'Ammi' or 'Mama'.\nMy father is the man who works for our family. I call him 'Abba' or 'Papa'.\nMy sister is a girl. She is older than me. I call her 'Bajee'.\nMy brother is a boy. He is younger than me.\nMy grandmother is my father's mother. I call her 'Dadi'.\nMy grandfather is my father's father. I call him 'Dada'.\n\nSome families are small. Some families are big. All families are special.", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "866e501c-b4ab-5a4c-b629-12d4c17da92b", "code": "V1-01-a", "statement": "Use everyday social/family vocabulary in context."}, {"sub_slo_id": "29880190-83a2-5b13-8fd6-f662e1b493e6", "code": "G1-01-a", "statement": "Recognise proper nouns (names of people)."}]}, {"topic_id": "bac80598-245e-5951-ba5c-8d445e8a59c2", "title": "This Is My Family", "topic_text": "Look at the picture of Ali's family.\nAli says, 'This is my family. We are six people.'\n\nAli points to each person:\n  This is my mother. Her name is Fatima.\n  This is my father. His name is Imran.\n  This is my sister. Her name is Ayesha.\n  This is my brother. His name is Bilal.\n  This is my grandmother. Her name is Zaitun.\n  This is my grandfather. His name is Yousuf.\n\nNames are special words. We always write a name with a capital letter at the start.\nLook: Fatima. Imran. Ayesha. Each name starts with a big letter.", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "b367e95a-859e-5d68-a510-5dda9c379847", "code": "W1-04-b", "statement": "Copy short sentences legibly."}, {"sub_slo_id": "866e501c-b4ab-5a4c-b629-12d4c17da92b", "code": "V1-01-a", "statement": "Use everyday social/family vocabulary in context."}, {"sub_slo_id": "999cec7e-5502-54d3-a246-87668df28a26", "code": "G1-01-b", "statement": "Capitalise proper nouns when writing."}]}, {"topic_id": "cffcca7c-61fe-5c65-afec-e65aeb13971b", "title": "I Love My Family", "topic_text": "I love my family. My family loves me.\nI have one mother. I have one father. I have one sister and one brother.\nWe live in a small house together.\n\nNow write about your own family.\nUse these sentence helpers:\n  My name is _______.\n  My mother's name is _______.\n  My father's name is _______.\n  I have _______ brothers and _______ sisters.\n\nRead your sentences out loud to a friend.\nListen carefully when your friend reads about their family.", "topic_text_truncated": false, "sub_slos": [{"sub_slo_id": "b367e95a-859e-5d68-a510-5dda9c379847", "code": "W1-04-b", "statement": "Copy short sentences legibly."}, {"sub_slo_id": "6080c732-baf8-5101-88c0-15b30538c864", "code": "G1-04-b", "statement": "Introduce oneself using 'My name is ___'."}]}], "chapter_slos": [{"code": "V1-01", "statement": "Use basic social-interaction and family vocabulary."}, {"code": "G1-01", "statement": "Recognise and capitalise proper nouns."}, {"code": "W1-04", "statement": "Copy short sentences legibly."}]}
```

## 4. Raw LLM response

_latency: **18.3s** · response length: 1495 chars_

```json
{"items": [{"kind": "lp", "topic_ids": ["2c32314a-2c05-526b-baee-a4e7ac9b5a85"], "lp_type": "comprehension_word_meanings", "sub_slo_ids": ["866e501c-b4ab-5a4c-b629-12d4c17da92b", "29880190-83a2-5b13-8fd6-f662e1b493e6"]}, {"kind": "lp", "topic_ids": ["2c32314a-2c05-526b-baee-a4e7ac9b5a85"], "lp_type": "reading", "sub_slo_ids": ["866e501c-b4ab-5a4c-b629-12d4c17da92b", "29880190-83a2-5b13-8fd6-f662e1b493e6"]}, {"kind": "lp", "topic_ids": ["bac80598-245e-5951-ba5c-8d445e8a59c2"], "lp_type": "grammar", "sub_slo_ids": ["29880190-83a2-5b13-8fd6-f662e1b493e6", "999cec7e-5502-54d3-a246-87668df28a26", "866e501c-b4ab-5a4c-b629-12d4c17da92b"]}, {"kind": "lp", "topic_ids": ["bac80598-245e-5951-ba5c-8d445e8a59c2"], "lp_type": "creative_writing", "sub_slo_ids": ["b367e95a-859e-5d68-a510-5dda9c379847", "999cec7e-5502-54d3-a246-87668df28a26"]}, {"kind": "fa", "topic_ids": ["2c32314a-2c05-526b-baee-a4e7ac9b5a85", "bac80598-245e-5951-ba5c-8d445e8a59c2"], "sub_slo_ids": ["866e501c-b4ab-5a4c-b629-12d4c17da92b", "29880190-83a2-5b13-8fd6-f662e1b493e6", "999cec7e-5502-54d3-a246-87668df28a26", "b367e95a-859e-5d68-a510-5dda9c379847"]}, {"kind": "lp", "topic_ids": ["cffcca7c-61fe-5c65-afec-e65aeb13971b"], "lp_type": "creative_writing", "sub_slo_ids": ["b367e95a-859e-5d68-a510-5dda9c379847", "6080c732-baf8-5101-88c0-15b30538c864"]}, {"kind": "fa", "topic_ids": ["cffcca7c-61fe-5c65-afec-e65aeb13971b"], "sub_slo_ids": ["b367e95a-859e-5d68-a510-5dda9c379847", "6080c732-baf8-5101-88c0-15b30538c864"]}]}
```

## 5. Parsed plan & validator verdict

- Parsed items: **7** · source: `llm`
- Validator: **PASS ✅**

| Period | Type | lp_type | Topic(s) | sub-SLOs |
|---|---|---|---|---|
| P1 | LESSON | `comprehension_word_meanings` | People in My Family | V1-01-a, G1-01-a |
| P2 | LESSON | `reading` | People in My Family | V1-01-a, G1-01-a |
| P3 | LESSON | `grammar` | This Is My Family | G1-01-a, G1-01-b, V1-01-a |
| P4 | LESSON | `creative_writing` | This Is My Family | W1-04-b, G1-01-b |
| P5 | **FORMATIVE** | — | People in My Family, This Is My Family | V1-01-a, G1-01-a, G1-01-b, W1-04-b |
| P6 | LESSON | `creative_writing` | I Love My Family | W1-04-b, G1-04-b |
| P7 | **FORMATIVE** | — | I Love My Family | W1-04-b, G1-04-b |

## 6. Performance & coverage

- Lessons: **5** · Formative assessments: **2** · Merged (multi-topic) lessons: **0**
- lp_type distribution: `comprehension_word_meanings`×1, `creative_writing`×2, `grammar`×1, `reading`×1
- Topic coverage: **3/3**
- Sub-SLO coverage: **5/5** — ✅ all covered
- Latency: **18.3s**

# References

Design lineage for **Cognitive Agent** — a continuously running cognitive agent with layered memory,
active archiving, and symbolic persona evolution.

**How to read this file.** Every entry cites a specific module or mechanism in this repository.
The `Applies to:` line under each reference names the file, config key, or design decision that the
work supports. Cross-references elsewhere in this document use the bracketed number
(e.g. `[18]`).

**Citation style.** APA-like; author lists are truncated after six names with `et al.`;
one entry per line so the list can be copied without reformatting.

**Status.** 67 works. Sections 1–14 are the bibliography, grouped by theme and numbered.
Section 15 maps each subsystem to its source. Section 16 lists the gaps the literature exposes.
Section 17 is the alphabetical index; section 18 collects repositories and tools.

**Revision note (2026-11-12).** Entries [41]–[67] were added after the P3 update of the codebase.
[41]–[44] cover the durable task queue and retry semantics, [45]–[51] the rate limit and the
memory bounds, [52]–[55] the human-in-the-loop memory gate, [56]–[60] temporal belief reasoning
and narrative continuity, [61]–[64] social intelligence and companion risk, and [65]–[67] the
web security primitives of the local API.

---

## 1. Cognitive architectures and memory hierarchy

[1] Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Terry, M. S. (2023). Generative Agents: Interactive Simulacra of Human Behavior. UIST '23. — https://arxiv.org/abs/2304.03442
    Applies to: the closest widely cited predecessor. Memory stream → `topic` / `experience` tables and the vector index over topic summaries. Reflection → `self_view` updates, persona narrative snapshots, and the daily narrative (`kind='daily'` topics). Planning / summarization over the stream → `maintenance.py --daily` consolidation.

[2] Sumers, T. R., Yao, X., Narasimhan, K., & Griffiths, T. L. (2024). Cognitive Architectures for Language Agents. TMLR. — https://arxiv.org/abs/2309.02427
    Applies to: the taxonomy this project follows — working / episodic / semantic / procedural memory plus a structured decision loop. Supports the layering in README §4 and the boundary argument in README §13 ("structural simulation, not consciousness").

[3] Packer, C., Ramaswamy, V., Martin, J. H., Han, X., Xu, Y., Raj, K., Gumbsch, C., et al. (2023). MemGPT: Towards LLMs as Operating Systems. — https://arxiv.org/abs/2310.08560
    Applies to: virtual context management and paging between memory tiers. Directly motivates the emergency-compression design — `MAX_SAFE_TOKENS`, `KEEP_RECENT_ROUNDS`, `HISTORY_INJECT_ROUNDS`, `MAX_COMPRESS_PASSES` in `config.py`.

[4] Anderson, J. R. (2004). An Integrated Theory of the Mind. MIT Press. — http://zoo.cs.yale.edu/classes/cs671/12f/12f-papers/anderson-act-r.pdf
    Applies to: the ACT-R basis for activation decay and chunk-based memory. Supports the mood decay model (`MOOD_DECAY_LAMBDA_HOUR`, half-life ≈ 35 h), the per-turn decay (`MOOD_DECAY_PER_TURN`), and belief strengthening via `confidence` increments in `cognitive/storage/kg_store.py`.

[5] Anderson, J. R., & Lebiere, C. (1998). ACT-R: A Cognitive Architecture for Modeling Cognition.
    Applies to: the original ACT-R specification; the reference for the chunk-based memory model underlying the decay parameters in `cognitive/persona/kernel.py`.

[6] Taatgen, N., Lebiere, C., & Anderson, J. R. (2011). Modeling paradigms in ACT-R. — https://www.ai.rug.nl/~niels/publications/taatgenLebiereAnderson.pdf
    Applies to: formal account of ACT-R's memory module — activation, decay, retrieval. Reference for the decay curves implemented in `cognitive/persona/kernel.py`.

---

## 2. Consolidation, hierarchical retrieval, and forgetting

[7] Sarthi, P., Abdullah, S., Tuli, V., Khemani, V., et al. (2024). RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval. ICLR '24. — https://arxiv.org/abs/2401.18059
    Applies to: recursive clustering + summarization into a hierarchy, retrieved at multiple granularities. Maps onto the promotion of `topic(kind='normal')` into `topic(kind='daily')` and the multi-granularity recall path in `cognitive/cognition/router.py`.

[8] Gutiérrez, B. J., Shu, Y., Su, W., et al. (2024). HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. NeurIPS '24. — https://arxiv.org/abs/2405.14831
    Applies to: hippocampal indexing theory applied to retrieval over a knowledge graph. The natural second option for `VectorStore.add/search/count` — the "Embedding backend" item in `docs/improvement-plan.md`.

[9] Xu, W., et al. (2025). A-MEM: Agentic Memory for LLM Agents. NeurIPS '25. — https://neurips.cc/media/neurips-2025/Slides/119020.pdf
    Applies to: Zettelkasten-style notes with explicit links and memory evolution. Comparable to the topic/experience link model and to retaining overturned beliefs (`SHOW_OVERTURNED_BELIEFS`) instead of deleting them.

[10] Tan, Z., et al. (2025). Reflective Memory Management for Long-term Dialogue Agents. ACL '25. — https://aclanthology.org/2025.acl-long.413
    Applies to: forward- and backward-facing reflection over long-term memory. The two-channel design here — per-turn active archiving plus daily/event-level consolidation — is an instance of this pattern.

[11] Honda, Y., et al. (2025). Human-Like Remembering and Forgetting in LLM Agents. — https://doi.org/10.1145/3765766.3765803
    Applies to: applies ACT-R-style time-based forgetting curves to agent memory chunks. The citable basis for the "Importance-Based Memory Decay" item listed as optional in `docs/improvement-plan.md`.

---

## 3. Persona and role consistency

[12] Zhang, S., Kiros, J., & Ba, J. (2018). Personalizing Dialogue Agents: I have a dog, do you have pets too? — https://arxiv.org/abs/1804.08166
    Applies to: the origin of persona-driven dialogue — a fixed persona profile conditioning generation. Directly underlies `data/persona/profile.json` (7 groups, 39 entries) as a non-rewritable baseline.

[13] Song, H., et al. (2020). Generating Persona Consistent Dialogues by Exploiting Large-Scale Persona Data. AAAI '20. — https://ojs.aaai.org/index.php/AAAI/article/view/6417/6273
    Applies to: persona consistency as an explicit evaluation target; motivates the persona-stability checks in `tests/eval/run_eval.py`.

[14] Chen, R., et al. (2025). Persona Vectors: Monitoring and Controlling Character Traits in Language Models. — https://arxiv.org/abs/2507.21509
    Applies to: the contrast case — personality controlled by directions in the model's activation space. This project takes a different route (symbolic scalar parameters injected as text), so the pair makes the design trade-off explicit.

[15] Sun, S., et al. (2025). Modulating Personality of Large Language Models by Merging Personality Vectors. EMNLP '25. — https://aclanthology.org/2025.emnlp-main.1253
    Applies to: a second parameterization of personality; a second reference point for the 14-parameter kernel.

[16] Ji, K., Lian, Y., Li, L., Gao, J., Li, W., & Dai, B. (2025). Enhancing Persona Consistency for LLMs' Role-Playing using Persona-Aware Contrastive Learning. — https://arxiv.org/abs/2503.17662
    Applies to: persona consistency under multi-turn drift, and how to evaluate it (CharEval + GPT-4 + human expert evaluation).

---

## 4. Belief conflict, provenance, and knowledge updating

[17] Rasmussen, P., et al. (2025). Zep: A Temporal Knowledge Graph Architecture for Agent Memory. — https://arxiv.org/abs/2501.13956
    Applies to: dual-timeline facts (when a fact was true vs. when it was learned) and explicit invalidation. Structurally close to the `valid_from` / `valid_to` window and the `is_active` invalidation in `kg_store.py`. Open-source implementation: https://github.com/getzep/graphiti

[18] Meng, F., Wu, J., & McAuley, J. (2026). BELIEFMEM: Belief-Revising Memory for Conversational LLM Agents. Findings of EMNLP '26, pp. 12152–12166. — https://doi.org/10.18653/2026.findings-emnlp.576
    Applies to: the closest theoretical match in the literature. Uses the AGM (Alchourrón–Gärdenfors–Makinson) framework to classify every claim into four actions — `exp` / `rev` / `dup` / `con` — and never deletes superseded beliefs. Those four map almost one-to-one onto this project's code-level rules: `exp` ↔ multi-value coexistence, `rev` ↔ conflict invalidation, `dup` ↔ reinforcement (`confidence += 0.05`), `con` ↔ single-value supersession. Also the direct citation for the append-only `belief_correction` ledger and the `active` / `candidate` / `rejected` status model.

[19] Estey-Ang, A., et al. (2026). A Governed Cognitive Architecture for Persistent AI Memory. — https://www.tdcommons.org/cgi/viewcontent.cgi?article=10947&context=dpubs_series
    Applies to: a multi-layer governance stack over the full memory lifecycle (acquisition → belief state → maintenance). The methodological frame for the provenance / confidence / correction design implemented in P1.

---

## 5. Proactivity and social-relationship modelling

[20] Deng, Y., et al. (2023). A Survey on Proactive Dialogue Systems: Problems, Methods, and Prospects. IJCAI '23 Survey Track. — https://arxiv.org/abs/2305.02750
    Applies to: the canonical survey on proactivity. Motivates letting the model choose the next contact interval (`decide_delay_minutes`) rather than using a fixed timer.

[21] Deng, Y., et al. (2025). Proactive Conversational AI: A Comprehensive Survey of Advancements and Opportunities. ACM Computing Surveys. — https://doi.org/10.1145/3715097
    Applies to: current survey of proactive mechanisms, including when-not-to-be-proactive. Background for the DND window, daily cap, and cooldown controls added in P2, and for the topic cooldown (`REMEMBER_COOLDOWN_MINUTES`) that stops the same memory from being raised twice in a row.

[22] Ortony, A., Clore, G. L., & Collins, A. (1988). The Cognitive Structure of Emotion. Cambridge University Press.
    Applies to: the OCC appraisal model — the psychological basis for representing emotion as a function of event appraisal, and for the affection state machine's ordered thresholds (`normal ≥ 30`, `cold < 30`, `broken < 12`, `reconcile ≥ 60`).

[23] Steunebrink, B. R., & Havinga, M. (2011). The OCC Model Revisited. KI. — https://www.idsia.ch/~steunebrink/Publications/KI09_OCC_revisited.pdf
    Applies to: formal restatement of OCC's 22 emotion types and their appraisal structure.

[24] Schweizer, S., & von Rosenberg, M. W. (2021). Psycho-informatics: Perspectives on the Appraisal Mechanism. MIT Press.
    Applies to: personality traits → appraisal → affect; the trait-to-emotion path this project approximates with the persona kernel and the `MOOD_MODE_WHITELIST`.

---

## 6. Retrieval strategy and "when should we retrieve"

[25] Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS '20.
    Applies to: the RAG baseline that this project's fallback layer deliberately does not lead with.

[26] Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024). Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. ICLR '24. — https://arxiv.org/abs/2310.11511
    Applies to: the source of the retrieve-on-demand pattern — a model decides whether retrieval is needed. Directly motivates the information-sufficiency judge (`cognitive/cognition/judge.py`) and the "persona first, retrieval optional" ordering in README §3.

[27] Yan, S. Q., et al. (2024). Corrective Retrieval Augmented Generation (CRAG). — https://arxiv.org/abs/2401.15884
    Applies to: quality-gated retrieval with self-correction. The reference for the bounded loop's stopping rules: `RAG_LOOP_STOP_ON_EMPTY`, `RAG_LOOP_DUP_RATIO`, and the forced conclusion on the final round.

[28] Madaan, A., et al. (2023). Self-Refine: Iterative Refinement with Self-Feedback. NeurIPS '23. — https://arxiv.org/abs/2303.17651
    Applies to: self-generated feedback loops; the pattern behind the narrative generator and the persona-drift description thresholds (`PERSONA_DESC_STRONG` / `MID` / `WEAK`).

[29] Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). Reflexion: Language Agents with Verbal Reinforcement Learning. NeurIPS '23. — https://arxiv.org/abs/2303.11366
    Applies to: learning from linguistic feedback rather than weight updates — the same stance taken here by storing memories and changelogs instead of fine-tuning.

[30] Wang, G., Xie, Y., Jiang, Y., Mandlekar, A., Sidford, C., Zaki, H. S., & Song, S. (2023). Voyager: An Open-Ended Embodied Agent with Large Language Models. — https://arxiv.org/abs/2305.16291
    Applies to: skill-library accumulation and automatic curriculum as lifelong-learning structures; a comparator for the accumulating, self-extending memory in this project.

[31] Park, J. S., Popowski, T., et al. (2022). Social Simulacra: Creating Populated Prototypes for Social Computing Systems. UIST '22. — https://arxiv.org/abs/2208.04024
    Applies to: population-level simulation with persistent agents; the reference for believable, relation-bearing agent behaviour at scale.

---

## 7. Evaluation and reliability

[32] Wu, D., Wang, H., Wen, Y., Yu, Z., et al. (2024). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. ICLR '25. — https://arxiv.org/abs/2410.10813
    Applies to: five long-term memory abilities — information extraction, multi-session reasoning, temporal reasoning, knowledge update, and abstention. The knowledge-update subtask is the closest external benchmark for this project's conflict-invalidation and multi-value rules, and the cheapest upgrade to the offline eval harness.

[33] Maharana, A., Lee, J., Tulyakov, V., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo). ACL '24. — https://aclanthology.org/2024.acl-long.747
    Applies to: 600-turn, ~16K-token conversations spanning up to 32 sessions. Provides the scale target the daily-consolidation cadence is designed to sustain, and is the benchmark used by [18].

[34] Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS '23. — https://arxiv.org/abs/2306.05685
    Applies to: the method for replacing rule-based assertions with model-scored rubric checks when `tests/eval/run_eval.py` graduates beyond offline retrieval and persona checks.

[35] Beyer, B., Jones, C., Petoff, N., & Murphy, N. R. (2016). The Site Reliability Engineering Book. Google. — https://sre.google/sre-book/table-of-contents/
    Applies to: the standard frame for the runtime-safety gap — service-level objectives, error budgets, monitoring, and incident response. The reference to cite when justifying error budgets, alerting, and fail-safe degradation for the API and scheduler tiers.

---

## 8. Surveys and reading lists

[36] Hu, Y., Liu, S., Yue, Y., Zhang, G., Liu, B., Zhu, F., Lin, J., Guo, H., et al. (2025). Memory in the Age of AI Agents. — https://arxiv.org/abs/2512.13564
    Applies to: the broadest agent-memory taxonomy available (forms, functions, dynamics). Curated paper list: https://github.com/Shichun-Liu/Agent-Memory-Paper-List

[37] Zhang, Z., Bo, X., Ma, C., Li, R., Chen, X., Dai, Q., et al. (2025). A Survey on the Memory Mechanism of Large Language Model based Agents. ACM TOIS 43(6). — https://doi.org/10.1145/3748302
    Applies to: the most-cited survey of LLM agent memory mechanisms; a systematic counterpart to [36].

[38] Zhou, C., Chai, H., Chen, W., Guo, Z., Shan, R., Song, Y., Xu, T., Yang, Y., et al. (2026). Externalization in LLM Agents: A Unified Review of Memory, Skills, Protocols and Harness Engineering. — https://arxiv.org/abs/2604.08224
    Applies to: frames this project precisely — agent capability is externalized into memory stores and harness engineering rather than model weights. The Chinese-language edition is at https://www.alphaxiv.org/zh/abs/2604.08224

[39] 陈旭 (2024). 基于大语言模型的自主智能体概述. CCL 2024, 中国中文信息学会计算语言学专业委员会. — https://aclanthology.org/2024.ccl-2.8.pdf
    Applies to: 中文综述，含记忆模块的结构、格式与操作；适合作为 README 中文版 §1 的引言依据。

[40] ysymyth (2024). awesome-language-agents. — https://github.com/ysymyth/awesome-language-agents
    Applies to: curated index of LLM-agent papers; includes a CoALA-based memory taxonomy and an implementation list.

---

## 9. Durable background work, retries, and idempotency

[41] Stonebraker, M., Zhou, X., Kraft, P., & Li, Q. (2026). Consistency and Correctness in Data-Oriented Workflow Systems. CIDR '26. — https://www.vldb.org/cidrdb/papers/2026/p9-stonebraker.pdf
    Applies to: the `task` table (`cognitive/storage/database.py`) and `TaskStore` in `cognitive/storyline.py` — a durable, resumable queue whose state (`status`, `retry_count`, `max_retries`, `next_run_ts`) lives in the same SQLite database as the data it produces, and whose `unique (space_id, action, params)` constraint is a natural idempotency key. The paper's AC/DC argument (durability alone is insufficient; a workflow needs atomicity across its steps) states the criterion this queue does not yet meet: the side effect and the task-state update are two separate commits.

[42] Kleppmann, M. (2017). Designing Data-Intensive Applications. O'Reilly.
    Applies to: the transactional substrate under the queue and the archiving path — single-writer SQLite, transactional update of related rows, and the pattern of deriving an idempotency key from content rather than from time. Here that key is the per-turn `turn_id` written onto `topic` rows, which makes re-archiving the same turn a no-op (`MemoryArchiver` in `cognitive/cognition/archiver.py`).

[43] Amazon Web Services (2019). Making Retries Safe with Idempotent APIs. AWS Builders' Library. — https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
    Applies to: the contract the queue assumes when `_run_tasks` (`cognitive/engine.py`) resumes a task that may already have partially executed — a retried step must be safe to run twice, and the caller must be able to tell "already done" from "not yet done".

[44] Brooker, M. (2019). Timeouts, Retries, and Backoff with Jitter. AWS Builders' Library. — https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
    Applies to: the retry semantics of `TaskStore` (`max_retries = 3`, `next_run_ts`). It also names the missing ingredient: the current delay is fixed, so tasks that fail together retry together — jitter is what breaks that lockstep, and a retry budget (rather than a retry count) is what keeps a failing dependency from being hammered.

---

## 10. Rate limiting, capacity bounds, and tail latency

[45] Heinanen, J., & Guerin, R. (1999). RFC 2697: A Single Rate Three Color Marker. IETF Informational. — https://www.rfc-editor.org/info/rfc2697
    Applies to: the token-bucket formulation that the API's limiter approximates — `RATE_LIMIT_MAX` requests per 60 s per remote address in `_check_rate_limit` (`api/server.py`). The implementation uses a sliding-window log rather than a token bucket: stricter (no burst allowance) but O(n) memory per key, and per-process only.

[46] Dean, J., & Barroso, L. A. (2013). The Tail at Scale. Communications of the ACM 56(2), 74–80. — https://cacm.acm.org/research/the-tail-at-scale/
    Applies to: the reasoning behind bounding work rather than optimizing the average case — the tail-latency argument for a single-process agent that fans out to several LLM calls per turn. Also the reference frame for the queue-depth and LLM-latency-variance gaps in section 16.

[47] Miller, G. A. (1956). The magical number seven, plus or minus two. Psychological Review 63(2), 81–97.
    Applies to: the capacity argument behind the memory bounds — `MEMORY_CAP_NORMAL` (800) and `MEMORY_MAX_VECTORS` (300) in `config.py`, enforced in `cognitive/engine.py`, which clears the retrieved snippets and sets `memory.capped` instead of letting the prompt grow without limit.

[48] Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. Behavioral and Brain Sciences 24(1), 87–114.
    Applies to: the tighter bound that motivates keeping the *working* set small while the archive stays large — the working-memory / episodic-memory split the project implements (recent turns and the belief block in context; everything else on disk and retrieved on demand).

[49] Megiddo, N., & Modha, D. S. (2003). ARC: A Self-Tuning, Low Overhead Replacement Cache. USENIX FAST '03. — https://www.usenix.org/conference/fast-03/arc-self-tuning-low-overhead-replacement-cache
    Applies to: the replacement-policy design that the current bound still lacks — `MEMORY_CAP_NORMAL` stops retrieval rather than evicting, so a vector store that crosses the cap permanently loses recall instead of keeping its most useful subset. ARC is the reference for a policy that balances recency against frequency at low overhead.

[50] Zhang, Y., Yang, J., Yue, Y., Vigfusson, Y., & Rashmi, K. V. (2024). SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches. USENIX NSDI '24. — https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo
    Applies to: the drop-in replacement for an LRU-style policy if `VectorStore` ever moves from a hard cap to real eviction — a handful of lines of code, a better hit rate, and less churn than a full replacement algorithm.

[51] Liu, N. F., et al. (2024). Lost in the Middle: How Language Models Use Long Contexts. Transactions of the Association for Computational Linguistics 12, 157–173. — https://aclanthology.org/2024.tacl-1.9/
    Applies to: why the retrieval set must stay small and why the *position* of injected memory matters — the evidence that stuffing more snippets into the prompt lowers their usefulness. Supports `MEMORY_MAX_VECTORS` and the "persona first, retrieval optional" ordering of README §3.

---

## 11. Human-in-the-loop memory governance and selective belief writing

[52] Geifman, Y., & El-Yaniv, R. (2019). SelectiveNet: A Deep Neural Network with an Integrated Reject Option. ICML '19, PMLR 97, 2151–2159. — https://proceedings.mlr.press/v97/geifman19a.html
    Applies to: the reject option, generalized beyond classification. The candidate gate in `cognitive/cognition/archiver.py` (`_gate_relation`) is a reject option on the *write* path: a relation below `HIGH_IMPORTANCE` (0.85) is not written as active, and a high-importance one is written as `status = 'candidate'` until the user confirms it.

[53] Wilder, B., Horvitz, E., & Kamar, E. (2020). Learning to Complement Humans. IJCAI '20, pp. 1526–1533. — https://www.ijcai.org/proceedings/2020/212
    Applies to: the complementarity argument behind the gate — human attention should be spent only on the cases the model is not best at deciding on its own. The 确认 / 纠正 / 否决 buttons in the 记忆 tab of the web UI are the human side of that division of labour.

[54] Maini, P., Feng, Z., Schwarzschild, A., Lipton, Z. C., & Kolter, J. Z. (2024). TOFU: A Task of Fictitious Unlearning for LLMs. — https://arxiv.org/abs/2401.06121
    Applies to: the evaluation frame for "does the system behave as if this belief had never been learned?" — the reference standard for the 否决 button. The mechanisms differ and the difference matters: TOFU measures weight-level unlearning, while here a rejected belief is a database row that is deactivated but deliberately retained for audit (`belief_correction`, `status = 'rejected'`).

[55] Uddin, M., et al. (2026). From Recall to Forgetting: Benchmarking Long-Term Memory for Personalized Agents. Findings of ACL '26. — https://aclanthology.org/2026.findings-acl.1337
    Applies to: the evaluation axis the current harness (`tests/eval/run_eval.py`) does not measure — recall is measured (Recall@1 = Recall@3 = 1.000), forgetting is not. This is the cheapest missing benchmark for the candidate gate and the rejection ledger, and the natural successor to [32].

---

## 12. Temporal belief reasoning and narrative continuity

[56] Chen, W., Wang, X., & Wang, W. Y. (2021). A Dataset for Answering Time-Sensitive Questions. NeurIPS Datasets and Benchmarks 2021. — https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/1f0e3dad99908345f7439f8ffabdffc4-Abstract-round2.html
    Applies to: the temporal-reasoning task behind `PAST_CUE_PATTERN` and `KGStore.query_past_beliefs` (`cognitive/storage/kg_store.py`) — separating "现在值" (`valid_to > now`) from "过去值" (`superseded`), so that "以前喜欢吃什么" is answered from the old belief instead of being captured by the current one.

[57] Yang, K., Klein, D., Peng, N., & Tian, Y. (2023). DOC: Improving Long Story Coherence With Detailed Outline Control. ACL '23. — https://aclanthology.org/2023.acl-long.190/
    Applies to: the outline-control approach behind `StorylineStore` (`cognitive/storyline.py`, `long_run_state` table) — a small, explicit set of story events maintained over time so that later turns reference a persistent plan instead of free-associating. It is also the closest literature analogue to the `severance` → `reconcile` relationship arc.

[58] Yang, K., Klein, D., Peng, N., & Tian, Y. (2022). Re3: Generating Longer Stories With Recursive Reprompting and Revision. EMNLP '22. — https://aclanthology.org/2022.emnlp-main.296/
    Applies to: the recursive expand-and-revise structure of the storyline generator — a plan is expanded step by step and each step is revised against the plan that already exists, which is how `long_run_state.events` accumulates instead of being overwritten.

[59] Goel, H., & Zhu, H. (2025). LIFELONG SOTOPIA: Evaluating Social Intelligence of Language Agents Over Lifelong Social Interactions. — https://arxiv.org/abs/2506.12666
    Applies to: the benchmark for social behaviour across many episodes rather than one conversation — the reference for the multi-day arc the project is built around (the per-turn / daily / big-event cadences of README §4).

[60] Li, Z., Huang, Z., Wang, W., & Jin, Q. (2026). LongMP-Bench: A Benchmark for Multimodal Persona Understanding in Long-Term Dialogues. Findings of ACL '26, pp. 23132–23160. — https://aclanthology.org/2026.findings-acl.1159/
    Applies to: tracking persona *evolution* over long-term interaction while keeping identity consistent — the benchmark-level counterpart to the persona baseline / drift / pending model of README §5, and to the identity-consistency check in `tests/eval/run_eval.py`.

---

## 13. Social intelligence and companion risk

[61] Zhou, X., Zhu, H., Mathur, L., Zhang, R., Qi, Z., Yu, H., Morency, L.-P., Bisk, Y., Fried, D., Neubig, G., & Sap, M. (2024). SOTOPIA: Interactive Evaluation for Social Intelligence in Language Agents. ICLR '24. — https://proceedings.iclr.cc/paper_files/paper/2024/file/b3075b88e583a0e98d8b24338a613060-Paper-Conference.pdf
    Applies to: the evaluation frame for social goals, believability, and relationship dynamics — the closest external rubric for the affection state machine and for the relationship-temperature block injected into the prompt (`_render_affection_block`).

[62] Bowlby, J. (1969). Attachment and Loss, Vol. 1: Attachment. Basic Books.
    Applies to: the secure-base model behind the persona design — one continuous counterpart whose baseline moves only at daily settlement while the drift band absorbs day-to-day variation (README §5). The attachment tradition is also the origin of protest-withdrawal behaviour, which is exactly what the `severance` event dramatizes.

[63] De Freitas, J., & Cohen, I. G. (2025). Unregulated emotional risks of AI wellness apps. Nature Machine Intelligence 7, 813–815. — https://doi.org/10.1038/s42256-025-01051-5
    Applies to: the two named adverse outcomes — ambiguous loss and dysfunctional emotional dependence — that the project's `severance` / `reconcile` events and the `SEVERANCE_OPT_IN` switch are a narrow, product-level response to. The paper's central argument — that optimizing for engagement produces manipulative strategies — is the reason the hostile-relief behaviour is opt-in rather than always-on.

[64] Editorial (2025). Emotional risks of AI companions demand attention. Nature Machine Intelligence 7, 981–982. — https://doi.org/10.1038/s42256-025-01093-9
    Applies to: the editorial position that transparency about the limits of simulated empathy is a core design principle, not an afterthought. README §13's "structural simulation of personhood, not consciousness" is the same commitment stated at the documentation level.

---

## 14. Web security primitives for the local API

[65] Barth, A. (2011). RFC 6454: The Web Origin Concept. IETF Standards Track. — https://www.rfc-editor.org/info/rfc6454/
    Applies to: the semantics of the `Origin` header that `PRIVACY_ALLOWED_ORIGINS` and `_check_origin` (`api/server.py`) depend on — an origin is a scheme/host/port triple, and it is the browser-supplied signal that a request is cross-origin.

[66] Jones, M., & Hardt, D. (2012). RFC 6750: The OAuth 2.0 Authorization Framework: Bearer Token Usage. IETF Standards Track. — https://www.rfc-editor.org/info/rfc6750/
    Applies to: the optional `API_TOKEN` check (`_check_api_token`) — a bearer token presented in the `Authorization` header. The RFC's warning that the token must be protected in transit is why the default origin allow-list is `127.0.0.1,localhost`.

[67] OWASP Foundation. Cross-Site Request Forgery Prevention Cheat Sheet. — https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
    Applies to: the origin / host allow-list as the documented defense against CSRF for a token-free local API, and the reason the check runs as request middleware (`_apply_protection`) rather than per route — every `/api/*` path is covered by construction.

---

## 15. Design lineage — what each subsystem derives from

- Layered memory (working → topic → belief → persona → narrative) ← [1] [2]. Topic-as-recall-unit and event-level recall differ from chunk-based RAG.
- Per-turn active archiving ← [1]. Archiving runs every turn, not only on demand.
- Emergency compression and token budgeting ← [3].
- Mood decay, activation decay, belief strengthening ← [4] [5] [6].
- Daily consolidation / narrative promotion ← [1] [7]. Normal topics are promoted into a daily narrative — hierarchy, not flat accumulation.
- Information-sufficiency judge ← [26]. Retrieval is conditional, not front-loaded.
- Bounded retrieval loop and stopping rules ← [27].
- Narrative generator and drift-threshold description ← [28].
- Self-improvement without weight updates ← [29].
- Long-term skill/knowledge accumulation ← [30].
- Believable multi-agent behaviour at scale ← [31].
- Symbolic persona kernel (14 scalars; baseline / drift / pending) ← [12] [13]. Contrasted with [14] [15] [16], which control personality in activation space or by fine-tuning.
- Multi-value beliefs and conflict invalidation ← [17] [18]. Rules implemented in code (testable) rather than left to the model.
- Belief provenance and correction ledger ← [18] [19]. `user_stated` / `model_inferred` / `user_corrected` / `seed` provenance with an append-only audit trail.
- Affection state machine ← [22] [23] [24]. Ordered thresholds with a deliberate hysteresis gap (reconcile line > cold line).
- Model-decided proactive contact ← [20].
- Proactive guarantees (single-use, due-only, anti-flood) and DND controls ← [21].
- Durable, resumable background task queue ← [41] [42] [43] [44]. State in the same database as the data; `unique (space_id, action, params)` as the idempotency key; `max_retries` / `next_run_ts` as the retry policy.
- Per-origin rate limiting ← [45]. Sliding window per remote address, applied as request middleware.
- Bounded memory (hard cap → stop recall) ← [47] [48] [49] [50] [51]. Capacity constants, the `memory.capped` flag, and the `memory_bound` statistics table.
- Candidate gate on high-importance beliefs ← [52] [53]. Model writes a candidate; the user confirms, corrects, or rejects.
- Explicit rejection with retention for audit ← [54] [55]. The rejected belief is kept, not deleted — the memory-system analogue of a right to be forgotten.
- Temporal belief separation (current value vs. past value) ← [56] [17].
- Storyline / narrative continuity across days ← [57] [58]. `long_run_state` keeps an explicit, revisable plan.
- Multi-day social arc and persona-evolution evaluation ← [59] [60] [61].
- Secure-base persona ← [62].
- Companion-risk awareness and opt-in severance ← [63] [64].
- Origin allow-list and optional bearer token ← [65] [66] [67].
- Offline TF-IDF retrieval ← deliberate divergence from [7] [8] [9]. Chosen for explainability and zero embedding dependency; the cost is a lower recall ceiling.
- Long-term memory evaluation ← [32] [33]. Model-scored rubric checks ← [34].
- Runtime objectives, error budgets, alerting ← [35].

---

## 16. Gaps the literature exposes — optional future work

Each item corresponds to an entry already listed as optional in `docs/improvement-plan.md`, or to a
mechanism that the P3 update introduced but did not yet take past its first version.

- Embedding backend for `VectorStore` ← [7] [8] [9].
- Quantified forgetting / importance-based decay ← [4] [11].
- External worker for proactive contact ← [3] (tiered memory under an external runtime) plus a durable task queue ← [41].
- Knowledge-update benchmarks ← [32] (knowledge-update subtask); compare directly against [18].
- Belief-governance formalization ← [17] [18] [19].
- Runtime objectives, error budgets, alerting ← [35].
- Broader externalization framing ← [37] [38].
- Eviction instead of a hard cap ← [49] [50]. Today `MEMORY_CAP_NORMAL` stops vector recall and leaves the store growing, so the first N documents keep crowding out everything newer.
- Multi-process execution of the queue and the limiter ← [41] [46]. `_RATE_BUCKETS` and `_run_tasks` are per-process, so a multi-worker deployment would multiply the effective limit and duplicate the queue drain.
- Jittered backoff and a retry budget ← [44]. The fixed `next_run_ts` delay retries a synchronised batch in lockstep.
- Atomic side-effect plus task-state update ← [41] [42]. A crash between the two commits leaves a task marked done whose effect is missing, or the reverse.
- Forgetting and rejection benchmarks ← [54] [55]. The harness measures recall only; it never checks that a rejected belief stops influencing answers.
- Social-intelligence and multi-day evaluation ← [59] [60] [61]. The current eval is single-turn retrieval plus persona stability.
- Long-context position effects ← [51]. Nothing in the harness checks that the injected belief block is read, rather than buried.

---

## 17. Alphabetical index

### A

**[4]** Anderson, J. R. (2004). *An Integrated Theory of the Mind.* MIT Press.
**[5]** Anderson, J. R., & Lebiere, C. (1998). *ACT-R: A Cognitive Architecture for Modeling Cognition.*
**[43]** Amazon Web Services (2019). *Making Retries Safe with Idempotent APIs.* AWS Builders' Library.
**[26]** Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024). Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection. ICLR '24.

### B

**[65]** Barth, A. (2011). RFC 6454: The Web Origin Concept. IETF Standards Track.
**[35]** Beyer, B., Jones, C., Petoff, N., & Murphy, N. R. (2016). *The Site Reliability Engineering Book.* Google.
**[62]** Bowlby, J. (1969). *Attachment and Loss, Vol. 1: Attachment.* Basic Books.
**[44]** Brooker, M. (2019). *Timeouts, Retries, and Backoff with Jitter.* AWS Builders' Library.

### C

**[14]** Chen, R., et al. (2025). Persona Vectors: Monitoring and Controlling Character Traits in Language Models.
**[56]** Chen, W., Wang, X., & Wang, W. Y. (2021). A Dataset for Answering Time-Sensitive Questions. NeurIPS Datasets and Benchmarks 2021.
**[48]** Cowan, N. (2001). The magical number 4 in short-term memory: A reconsideration of mental storage capacity. *Behavioral and Brain Sciences* 24(1).

### D

**[46]** Dean, J., & Barroso, L. A. (2013). The Tail at Scale. *Communications of the ACM* 56(2).
**[63]** De Freitas, J., & Cohen, I. G. (2025). Unregulated emotional risks of AI wellness apps. *Nature Machine Intelligence* 7.
**[20]** Deng, Y., et al. (2023). A Survey on Proactive Dialogue Systems: Problems, Methods, and Prospects. IJCAI '23 Survey Track.
**[21]** Deng, Y., et al. (2025). Proactive Conversational AI: A Comprehensive Survey of Advancements and Opportunities. ACM Computing Surveys.

### E

**[19]** Estey-Ang, A., et al. (2026). A Governed Cognitive Architecture for Persistent AI Memory.
**[64]** Editorial (2025). Emotional risks of AI companions demand attention. *Nature Machine Intelligence* 7.

### G

**[52]** Geifman, Y., & El-Yaniv, R. (2019). SelectiveNet: A Deep Neural Network with an Integrated Reject Option. ICML '19.
**[59]** Goel, H., & Zhu, H. (2025). LIFELONG SOTOPIA: Evaluating Social Intelligence of Language Agents Over Lifelong Social Interactions.
**[8]** Gutiérrez, B. J., Shu, Y., Su, W., et al. (2024). HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. NeurIPS '24.

### H

**[45]** Heinanen, J., & Guerin, R. (1999). RFC 2697: A Single Rate Three Color Marker.
**[11]** Honda, Y., et al. (2025). Human-Like Remembering and Forgetting in LLM Agents.
**[36]** Hu, Y., Liu, S., Yue, Y., Zhang, G., Liu, B., Zhu, F., Lin, J., Guo, H., et al. (2025). Memory in the Age of AI Agents.

### J

**[16]** Ji, K., Lian, Y., Li, L., Gao, J., Li, W., & Dai, B. (2025). Enhancing Persona Consistency for LLMs' Role-Playing using Persona-Aware Contrastive Learning.
**[66]** Jones, M., & Hardt, D. (2012). RFC 6750: The OAuth 2.0 Authorization Framework: Bearer Token Usage. IETF Standards Track.

### K

**[42]** Kleppmann, M. (2017). *Designing Data-Intensive Applications.* O'Reilly.

### L

**[25]** Lewis, P., Perez, E., Piktus, A., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS '20.
**[60]** Li, Z., Huang, Z., Wang, W., & Jin, Q. (2026). LongMP-Bench: A Benchmark for Multimodal Persona Understanding in Long-Term Dialogues. Findings of ACL '26.
**[51]** Liu, N. F., et al. (2024). Lost in the Middle: How Language Models Use Long Contexts. *TACL* 12.

### M

**[28]** Madaan, A., et al. (2023). Self-Refine: Iterative Refinement with Self-Feedback. NeurIPS '23.
**[33]** Maharana, A., Lee, J., Tulyakov, V., et al. (2024). Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo). ACL '24.
**[54]** Maini, P., Feng, Z., Schwarzschild, A., Lipton, Z. C., & Kolter, J. Z. (2024). TOFU: A Task of Fictitious Unlearning for LLMs.
**[49]** Megiddo, N., & Modha, D. S. (2003). ARC: A Self-Tuning, Low Overhead Replacement Cache. FAST '03.
**[18]** Meng, F., Wu, J., & McAuley, J. (2026). BELIEFMEM: Belief-Revising Memory for Conversational LLM Agents. Findings of EMNLP '26.
**[47]** Miller, G. A. (1956). The magical number seven, plus or minus two. *Psychological Review* 63(2).

### O

**[22]** Ortony, A., Clore, G. L., & Collins, A. (1988). *The Cognitive Structure of Emotion.* Cambridge University Press.
**[67]** OWASP Foundation. Cross-Site Request Forgery Prevention Cheat Sheet.

### P

**[3]** Packer, C., Ramaswamy, V., Martin, J. H., et al. (2023). MemGPT: Towards LLMs as Operating Systems.
**[1]** Park, J. S., O'Brien, J. C., Cai, C. J., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. UIST '23.
**[31]** Park, J. S., Popowski, T., et al. (2022). Social Simulacra: Creating Populated Prototypes for Social Computing Systems. UIST '22.

### R

**[17]** Rasmussen, P., et al. (2025). Zep: A Temporal Knowledge Graph Architecture for Agent Memory.

### S

**[7]** Sarthi, P., Abdullah, S., Tuli, V., Khemani, V., et al. (2024). RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval. ICLR '24.
**[24]** Schweizer, S., & von Rosenberg, M. W. (2021). *Psycho-informatics: Perspectives on the Appraisal Mechanism.* MIT Press.
**[29]** Shinn, N., Cassano, F., Berman, E., et al. (2023). Reflexion: Language Agents with Verbal Reinforcement Learning. NeurIPS '23.
**[13]** Song, H., et al. (2020). Generating Persona Consistent Dialogues by Exploiting Large-Scale Persona Data. AAAI '20.
**[23]** Steunebrink, B. R., & Havinga, M. (2011). The OCC Model Revisited. KI.
**[41]** Stonebraker, M., Zhou, X., Kraft, P., & Li, Q. (2026). Consistency and Correctness in Data-Oriented Workflow Systems. CIDR '26.
**[2]** Sumers, T. R., Yao, X., Narasimhan, K., & Griffiths, T. L. (2024). Cognitive Architectures for Language Agents. TMLR.
**[15]** Sun, S., et al. (2025). Modulating Personality of Large Language Models by Merging Personality Vectors. EMNLP '25.

### T

**[6]** Taatgen, N., Lebiere, C., & Anderson, J. R. (2011). Modeling paradigms in ACT-R.
**[10]** Tan, Z., et al. (2025). Reflective Memory Management for Long-term Dialogue Agents. ACL '25.

### U

**[55]** Uddin, M., et al. (2026). From Recall to Forgetting: Benchmarking Long-Term Memory for Personalized Agents. Findings of ACL '26.

### W

**[30]** Wang, G., Xie, Y., Jiang, Y., et al. (2023). Voyager: An Open-Ended Embodied Agent with Large Language Models.
**[53]** Wilder, B., Horvitz, E., & Kamar, E. (2020). Learning to Complement Humans. IJCAI '20.
**[32]** Wu, D., Wang, H., Wen, Y., Yu, Z., et al. (2024). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. ICLR '25.

### X

**[9]** Xu, W., et al. (2025). A-MEM: Agentic Memory for LLM Agents. NeurIPS '25.

### Y

**[27]** Yan, S. Q., et al. (2024). Corrective Retrieval Augmented Generation.
**[58]** Yang, K., Klein, D., Peng, N., & Tian, Y. (2022). Re3: Generating Longer Stories With Recursive Reprompting and Revision. EMNLP '22.
**[57]** Yang, K., Klein, D., Peng, N., & Tian, Y. (2023). DOC: Improving Long Story Coherence With Detailed Outline Control. ACL '23.
**[40]** ysymyth (2024). *awesome-language-agents.*

### Z

**[12]** Zhang, S., Kiros, J., & Ba, J. (2018). Personalizing Dialogue Agents: I have a dog, do you have pets too?
**[50]** Zhang, Y., Yang, J., Yue, Y., Vigfusson, Y., & Rashmi, K. V. (2024). SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches. NSDI '24.
**[37]** Zhang, Z., Bo, X., Ma, C., Li, R., et al. (2025). A Survey on the Memory Mechanism of Large Language Model based Agents. ACM TOIS 43(6).
**[34]** Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS '23.
**[38]** Zhou, C., Chai, H., Chen, W., et al. (2026). Externalization in LLM Agents: A Unified Review of Memory, Skills, Protocols and Harness Engineering.
**[61]** Zhou, X., Zhu, H., Mathur, L., Zhang, R., et al. (2024). SOTOPIA: Interactive Evaluation for Social Intelligence in Language Agents. ICLR '24.

### 中文

**[39]** 陈旭 (2024). 基于大语言模型的自主智能体概述. CCL 2024, 中国中文信息学会计算语言学专业委员会.

---

## 18. Repositories and tools

**Graphiti** — open-source implementation of the temporal knowledge graph architecture in [17]. — https://github.com/getzep/graphiti
    Reference for the `valid_from` / `valid_to` and invalidation design in `cognitive/storage/kg_store.py`.

**Agent-Memory-Paper-List** — curated companion list for the survey in [36]. — https://github.com/Shichun-Liu/Agent-Memory-Paper-List
    Working bibliography for the agent-memory literature; useful when expanding section 2 or section 8.

**TOFU benchmark** — dataset and metrics for the fictitious-unlearning reference [54]. — https://locuslab.github.io/tofu/
    Reference for building the missing "did the rejected belief stop mattering?" evaluation.

**Celery / Amazon SQS** — production-scale counterparts of the `task` queue in [41] and [44], with dead-letter queues and visibility timeouts.
    Reference when the single-process `TaskStore` is replaced by an external worker.

**Redis eviction policies** — production documentation for the LRU / LFU / random eviction families discussed in [49] and [50].
    Reference for replacing the hard `MEMORY_CAP_NORMAL` stop with a real eviction policy.

**Envoy / NGINX request limiting** — production implementations of the sliding-window and token-bucket limiters described in [45].
    Reference for the shared-state rate limiter a multi-process deployment would need.

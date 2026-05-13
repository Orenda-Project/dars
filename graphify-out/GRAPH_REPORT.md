# Graph Report - dars  (2026-05-13)

## Corpus Check
- 116 files · ~107,576 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 952 nodes · 1973 edges · 69 communities detected
- Extraction: 56% EXTRACTED · 44% INFERRED · 0% AMBIGUOUS · INFERRED: 862 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 110|Community 110]]
- [[_COMMUNITY_Community 111|Community 111]]
- [[_COMMUNITY_Community 112|Community 112]]
- [[_COMMUNITY_Community 113|Community 113]]
- [[_COMMUNITY_Community 114|Community 114]]
- [[_COMMUNITY_Community 115|Community 115]]

## God Nodes (most connected - your core abstractions)
1. `Base` - 58 edges
2. `CreateTopicRequest` - 35 edges
3. `CreateSlotRequest` - 35 edges
4. `Full curriculum tree for the client's curriculum, filtered by grade and subject.` - 34 edges
5. `Generate (or regenerate) a lesson plan for a slot using its topic_text.` - 34 edges
6. `Fetch book info from core DB without importing anything.` - 34 edges
7. `Import a single book with OCR (book_text) into Dars.` - 34 edges
8. `Background task: run breakdown → LPs, skipping anything already done.     If cha` - 34 edges
9. `Queue LP generation for all slots in a chapter that have topic_text.` - 34 edges
10. `Client` - 33 edges

## Surprising Connections (you probably didn't know these)
- `Base` --uses--> `Tests for the school/ teacher-planning module.  Pattern follows test_auth.py / t`  [INFERRED]
  server/src/dars/database.py → server/tests/test_school.py
- `Base` --uses--> `Create a client via signup and return the raw API key.`  [INFERRED]
  server/src/dars/database.py → server/tests/test_school.py
- `Base` --uses--> `A second client (different client_id) for isolation tests.`  [INFERRED]
  server/src/dars/database.py → server/tests/test_school.py
- `Create a PENDING custom lesson plan record and return it. Background task fires` --uses--> `Client`  [INFERRED]
  server/src/dars/custom_lesson_plans/service.py → server/src/dars/clients/models.py
- `Look up active client by raw API key. Returns None if not found or inactive.` --uses--> `Client`  [INFERRED]
  server/src/dars/clients/service.py → server/src/dars/clients/models.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.17
Nodes (73): breakdown_chapter(), Admin service for curriculum breakdown.  Orchestrates the two-step AI pipeline (, Run the full AI breakdown pipeline for a chapter and persist results.      Steps, Book, BookChapter, Client, GeneratedLP, LessonSlot (+65 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (59): canonical_curriculum(), canonical_grade(), canonical_subject(), Canonical value mapping for curriculum, grade, and subject.  Dars stores subject, Normalise subject to canonical code. Returns value as-is if no alias found (DB w, Return canonical curriculum code, raise ValueError if unrecognised., Cast to int. DB will validate if it's a known grade., GeneratedExam (+51 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (69): Academic Calendar, ADR-001: FastAPI over Django REST, ADR-002: Row-Level Multi-Tenancy, ADR-003: Supabase for Database, ADR-004: API Keys over JWT, ADR-005: Delegate AI Generation to LP Assistant, API Key Auth (SHA-256 hashed), Async LP Generation (202 Accepted + BackgroundTasks) (+61 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (55): BaseModel, create_client_endpoint(), get_analytics(), list_clients_endpoint(), rotate_my_key(), RotateKeyResponse, AcademicYearCreate, AcademicYearListResponse (+47 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (49): Base, get_db(), DeclarativeBase, Grade, Subject, Assessment endpoint tests.  Anthropic API calls are mocked — no real network acc, Tests for:   POST /api/v1/custom-lesson-plans   GET  /api/v1/custom-lesson-plans, Return a mock httpx response that simulates LP assistant success. (+41 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (45): client(), get_current_client(), CurriculumData, SLO, update_client_endpoint(), create_client(), _generate_api_key(), get_client_by_api_key() (+37 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (43): Base, AcademicYear, AssessmentSlot, ChapterPlan, ClassLessonSlot, ClassSubjectTeacher, Holiday, SchoolClass (+35 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (49): ADR-001 Consequence: SQLAlchemy Replaces Django ORM, ADR-001: FastAPI over Django REST, ADR-001 Rationale: Async-Native for AI Service, ADR-001 Rationale: Auto-Generated OpenAPI, get_current_client Dependency (enforces client_id), ADR-002 Rationale: Simpler than Schema-per-Tenant, ADR-002: Row-Level Multi-Tenancy Decision, ADR-003 Rationale: No Local DB Container Needed (+41 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (29): handleAutoSchedule(), handleGenerate(), handleMarkTaught(), handleStatusChange(), openClass(), Ring(), ringColor(), addHoliday() (+21 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (29): import_books(), import_single_book(), list_known_books(), preview_book(), Import books and chapters from taleemabad-core into Dars., Fetch book metadata from core DB without writing anything to Dars.     Returns a, Import a single book (by arbitrary core_id + schema) including book_text (OCR)., Return the static book catalogue as dicts for the admin UI. (+21 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (31): api_key(), api_key2(), _assign_subject(), headers(), _make_academic_year(), _make_class(), Tests for the school/ teacher-planning module.  Pattern follows test_auth.py / t, Create a client via signup and return the raw API key. (+23 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (24): Teacher, get_teacher_endpoint(), list_teachers_endpoint(), login_endpoint(), Register a new client account.      Returns the API key once — store it securely, Authenticate and receive a rotated API key.      Every successful login issues a, Authenticate and receive a rotated API key.      Every successful login issues a, register_teacher_endpoint() (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.28
Nodes (17): _make_book(), _make_chapter(), _make_slot(), _make_topic(), test_breakdown_creates_topics_and_slots(), test_breakdown_forbidden_without_secret(), test_breakdown_replaces_existing(), test_list_slots_empty() (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (10): getApiKey(), handleImport(), handlePreview(), handleSubjectChange(), handleSubmit(), NoCurriculumBanner(), Spinner(), getApiKey() (+2 more)

### Community 14 - "Community 14"
Cohesion: 0.21
Nodes (16): build_bru(), build_sample_body(), clear_bru_files(), ensure_dev_env(), fetch_openapi(), get_auth_header(), main(), path_to_folder() (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.21
Nodes (12): _make_book(), _make_chapter(), test_list_books_filter_combined(), test_list_books_filter_curriculum(), test_list_books_filter_grade(), test_list_books_filter_subject(), test_list_books_returns_all(), test_list_chapters_empty() (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.17
Nodes (15): add_line_numbers(), clean_topic_title(), _extract_json_from_response(), _extract_topic_text(), format_topic_for_extraction(), Curriculum breakdown service — two-step AI pipeline ported from the Schema repo., Add 'Line: N - ' prefix to each line., Strip 'Topic 1:' style prefix from a section title. (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.42
Nodes (7): client_headers(), get_books(), get_chapters(), has_topics(), main(), Run AI topic breakdown for all book chapters in Dars.  Calls POST /api/v1/admin/, run_breakdown()

### Community 19 - "Community 19"
Cohesion: 0.39
Nodes (7): fetch_book(), fetch_chapters(), main(), Import books and chapters from taleemabad-core into Dars.  Sources:   ICT    → f, Upsert into dars.books, return the dars book id., upsert_book(), upsert_chapters()

### Community 20 - "Community 20"
Cohesion: 0.29
Nodes (5): lifespan(), _asyncpg_url(), Lightweight migration runner.  Scans supabase/migrations/*.sql in filename order, Convert SQLAlchemy URL scheme to plain asyncpg scheme., run_migrations()

### Community 21 - "Community 21"
Cohesion: 0.29
Nodes (4): WebhookDelivery, deliver_webhook(), test_deliver_webhook_failure_marks_failed_after_max_retries(), test_deliver_webhook_success()

### Community 22 - "Community 22"
Cohesion: 0.25
Nodes (8): content_json / answers_json Parallel Arrays, Curriculum Lock (ICT vs Punjab), Curriculum Tree API (GET /api/v1/curriculum), ICT Curriculum, Lesson Plans API, Punjab Curriculum, Student Assessment API, Teacher Assessment API (GET /api/v1/assessments)

### Community 23 - "Community 23"
Cohesion: 0.43
Nodes (8): File/Document Icon (generic file with folded corner and text lines), Globe/World Icon (circle with latitude/longitude grid lines), Dars App Icon (open book with spine, terra dot, dark background), Next.js Wordmark Logo (full NEXT.JS text in black), Vercel Logo (white upward-pointing triangle), Next.js webapp app directory, Next.js webapp public assets directory, Browser Window Icon (rounded rectangle with three traffic-light dots)

### Community 24 - "Community 24"
Cohesion: 0.43
Nodes (6): generate_lp(), get_chapter_slots(), main(), persist_lp(), Generate lesson plans for all slots in a chapter by calling UG LP with topic_tex, Insert LP into lesson_plans, update slot.lesson_plan_id, return lp_id.

### Community 25 - "Community 25"
Cohesion: 0.33
Nodes (6): Curriculum Data Layer (sub-SLOs, topics, join tables), Engine Migration (LP engine absorption), LP Breakdown Module, Phase 1: Curriculum-Driven LP Generation, LP Stub Generation (async per stub), UG_LessonPlan Service

### Community 26 - "Community 26"
Cohesion: 0.4
Nodes (2): BaseSettings, Settings

### Community 28 - "Community 28"
Cohesion: 0.4
Nodes (5): 202 Accepted Async Pattern, Synchronous 60-second Generation Issue, Supabase Connection Pool Saturation Risk, Broad Exception Handling in Generation, Job Queue (arq/pgqueuer)

### Community 29 - "Community 29"
Cohesion: 0.4
Nodes (5): Async Generation Pattern (202 PENDING → READY), Custom Exam Generations API (POST /api/v1/custom-exam-generations), Custom Lesson Plans API (POST /api/v1/custom-lesson-plans), Status Values (PENDING/READY/ERROR), WhatsApp Product (Phase 3.5)

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (4): MCP Server Strategic Value, @dars/node SDK Scaffold (unusable), @dars/mcp Server, @dars/node SDK

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (2): Documentation Types & Line Limits, YAML Frontmatter Convention

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (2): EG Integration, UG_EG Exam Generation Service

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Return canonical subject code, raise ValueError if unrecognised.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Return canonical curriculum code, raise ValueError if unrecognised.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Return canonical grade integer, raise ValueError if out of range.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Raise ValueError if subject is not valid for the given curriculum.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Create a PENDING lesson plan record and return it. Background task fires separat

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Create a PENDING exam generation record and return it. Background task fires sep

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Fetch a single exam generation, always filtering by client_id.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Return (items, total) for paginated exam generation list, always filtered by cli

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Background task: call EG Assistant, update ExamGeneration record, fire webhook.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Extract a JSON array from LLM response using two fallback strategies.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Split MCQs into questions-only and answers-only parallel lists.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Background task: generate MCQs from a lesson plan and update the assessment reco

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Fetch a single custom lesson plan, always filtering by client_id.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Return (items, total) for paginated custom lesson plan list, filtered by client_

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Background task: call LP Assistant, update CustomLessonPlan record.     Uses its

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Background task: submit to UG_EG v2 async endpoint, poll for result, update reco

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Extract a JSON array from LLM response using two fallback strategies.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Split MCQs into questions-only and answers-only parallel lists.

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Background task: generate student MCQs from a lesson plan and update the student

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Beads Work Tracking

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Structured Logging Convention

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Next.js Agent Rules (AGENTS.md)

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Webhook DLQ UI

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): Daily Make Commands

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): Supabase Environments (dars-dev, dars-prod)

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): API Key Format (dars_ prefix)

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Migration File Rules

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): metadata_ Field Naming Smell

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Cursor-Based Pagination (missing)

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): LP Deletion Endpoint (missing)

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): Rate Limiting (missing)

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): API Authentication (X-API-Key)

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (1): Analytics API (GET /api/v1/analytics)

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): external_id Concept

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): Exam Generation Service

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): Digital Coach Service

## Knowledge Gaps
- **165 isolated node(s):** `Infer auth header from path prefix.`, `Convert /api/v1/lesson-plans to lesson-plans, /admin/clients to admin.`, `Build a sample request body from the OpenAPI schema.`, `Delete all .bru files and subdirectories except environments/.`, `Run AI topic breakdown for all book chapters in Dars.  Calls POST /api/v1/admin/` (+160 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 26`** (5 nodes): `BaseSettings`, `cors_origins_list()`, `effective_core_db_url()`, `Settings`, `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `Documentation Types & Line Limits`, `YAML Frontmatter Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `EG Integration`, `UG_EG Exam Generation Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Return canonical subject code, raise ValueError if unrecognised.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Return canonical curriculum code, raise ValueError if unrecognised.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Return canonical grade integer, raise ValueError if out of range.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Raise ValueError if subject is not valid for the given curriculum.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Create a PENDING lesson plan record and return it. Background task fires separat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Create a PENDING exam generation record and return it. Background task fires sep`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Fetch a single exam generation, always filtering by client_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Return (items, total) for paginated exam generation list, always filtered by cli`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Background task: call EG Assistant, update ExamGeneration record, fire webhook.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Extract a JSON array from LLM response using two fallback strategies.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Split MCQs into questions-only and answers-only parallel lists.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Background task: generate MCQs from a lesson plan and update the assessment reco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Fetch a single custom lesson plan, always filtering by client_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Return (items, total) for paginated custom lesson plan list, filtered by client_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Background task: call LP Assistant, update CustomLessonPlan record.     Uses its`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Background task: submit to UG_EG v2 async endpoint, poll for result, update reco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Extract a JSON array from LLM response using two fallback strategies.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Split MCQs into questions-only and answers-only parallel lists.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Background task: generate student MCQs from a lesson plan and update the student`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Beads Work Tracking`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Structured Logging Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Next.js Agent Rules (AGENTS.md)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Webhook DLQ UI`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `Daily Make Commands`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `Supabase Environments (dars-dev, dars-prod)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `API Key Format (dars_ prefix)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Migration File Rules`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `metadata_ Field Naming Smell`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Cursor-Based Pagination (missing)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `LP Deletion Endpoint (missing)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `Rate Limiting (missing)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `API Authentication (X-API-Key)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `Analytics API (GET /api/v1/analytics)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `external_id Concept`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `Exam Generation Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `Digital Coach Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 4` to `Community 0`, `Community 1`, `Community 5`, `Community 6`, `Community 9`, `Community 10`, `Community 11`, `Community 21`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `Client` connect `Community 0` to `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `Tests for the school/ teacher-planning module.  Pattern follows test_auth.py / t` connect `Community 10` to `Community 4`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 56 inferred relationships involving `Base` (e.g. with `Client` and `WebhookDelivery`) actually correct?**
  _`Base` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `CreateTopicRequest` (e.g. with `Client` and `Book`) actually correct?**
  _`CreateTopicRequest` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `CreateSlotRequest` (e.g. with `Client` and `Book`) actually correct?**
  _`CreateSlotRequest` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `Full curriculum tree for the client's curriculum, filtered by grade and subject.` (e.g. with `Client` and `Book`) actually correct?**
  _`Full curriculum tree for the client's curriculum, filtered by grade and subject.` has 33 INFERRED edges - model-reasoned connections that need verification._
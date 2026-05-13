# Graph Report - dars  (2026-05-13)

## Corpus Check
- 128 files · ~124,356 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1156 nodes · 3670 edges · 74 communities detected
- Extraction: 38% EXTRACTED · 62% INFERRED · 0% AMBIGUOUS · INFERRED: 2269 edges (avg confidence: 0.54)
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
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 62|Community 62]]
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
- [[_COMMUNITY_Community 116|Community 116]]
- [[_COMMUNITY_Community 117|Community 117]]
- [[_COMMUNITY_Community 118|Community 118]]
- [[_COMMUNITY_Community 119|Community 119]]
- [[_COMMUNITY_Community 120|Community 120]]
- [[_COMMUNITY_Community 121|Community 121]]
- [[_COMMUNITY_Community 122|Community 122]]
- [[_COMMUNITY_Community 123|Community 123]]
- [[_COMMUNITY_Community 124|Community 124]]

## God Nodes (most connected - your core abstractions)
1. `Base` - 99 edges
2. `Client` - 94 edges
3. `BookChapter` - 88 edges
4. `Book` - 82 edges
5. `ChapterPlan` - 66 edges
6. `SchoolClass` - 65 edges
7. `ClassSubjectTeacher` - 65 edges
8. `AcademicYear` - 64 edges
9. `ClassLessonSlot` - 56 edges
10. `AssessmentSlot` - 56 edges

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
Cohesion: 0.08
Nodes (139): Base, Base, DeclarativeBase, AcademicYear, AssessmentSlot, Book, BookChapter, ChapterPlan (+131 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (96): breakdown_chapter(), Admin service for curriculum breakdown.  Orchestrates the two-step AI pipeline (, Run the full AI breakdown pipeline for a chapter and persist results.      Steps, import_books(), import_single_book(), list_known_books(), preview_book(), Import books and chapters from taleemabad-core into Dars. (+88 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (69): client(), get_current_client(), create_client_endpoint(), list_clients_endpoint(), rotate_my_key(), RotateKeyResponse, update_client_endpoint(), ClientAdminResponse (+61 more)

### Community 3 - "Community 3"
Cohesion: 0.16
Nodes (74): BaseModel, Teacher, get_analytics(), get_my_classes(), list_assessment_slots_flat(), list_lesson_slots_flat(), prefill_chapter_plans(), Return all ClassSubjectTeacher rows assigned to the client's default_teacher_id. (+66 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (53): commitEditTitle(), handleAutoSchedule(), handleBreakdownYear(), handleGenerate(), handleGenerateAll(), handleGenerateAllLPs(), handleGenerateExam(), handleGenerateLP() (+45 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (69): Academic Calendar, ADR-001: FastAPI over Django REST, ADR-002: Row-Level Multi-Tenancy, ADR-003: Supabase for Database, ADR-004: API Keys over JWT, ADR-005: Delegate AI Generation to LP Assistant, API Key Auth (SHA-256 hashed), Async LP Generation (202 Accepted + BackgroundTasks) (+61 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (56): canonical_curriculum(), canonical_grade(), canonical_subject(), Canonical value mapping for curriculum, grade, and subject.  Dars stores subject, Normalise subject to canonical code. Returns value as-is if no alias found (DB w, Return canonical curriculum code, raise ValueError if unrecognised., Cast to int. DB will validate if it's a known grade., create_exam_endpoint() (+48 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (40): add_assessment_slot(), add_holiday(), assign_subject(), auto_schedule_assessments(), breakdown_year(), bulk_upsert_chapter_plans(), create_academic_year(), create_class() (+32 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (49): ADR-001 Consequence: SQLAlchemy Replaces Django ORM, ADR-001: FastAPI over Django REST, ADR-001 Rationale: Async-Native for AI Service, ADR-001 Rationale: Auto-Generated OpenAPI, get_current_client Dependency (enforces client_id), ADR-002 Rationale: Simpler than Schema-per-Tenant, ADR-002: Row-Level Multi-Tenancy Decision, ADR-003 Rationale: No Local DB Container Needed (+41 more)

### Community 9 - "Community 9"
Cohesion: 0.16
Nodes (31): api_key(), api_key2(), _assign_subject(), headers(), _make_academic_year(), _make_class(), Tests for the school/ teacher-planning module.  Pattern follows test_auth.py / t, Create a client via signup and return the raw API key. (+23 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (10): getApiKey(), handleImport(), handlePreview(), handleSubjectChange(), handleSubmit(), NoCurriculumBanner(), Spinner(), getApiKey() (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.21
Nodes (16): build_bru(), build_sample_body(), clear_bru_files(), ensure_dev_env(), fetch_openapi(), get_auth_header(), main(), path_to_folder() (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.21
Nodes (12): _make_book(), _make_chapter(), test_list_books_filter_combined(), test_list_books_filter_curriculum(), test_list_books_filter_grade(), test_list_books_filter_subject(), test_list_books_returns_all(), test_list_chapters_empty() (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.25
Nodes (14): _assign_subject(), _get_me(), headers(), _make_academic_year(), _make_class(), Tests for Step 7 — Teacher App endpoint:   GET /api/v1/me/classes, GET /api/v1/me/classes returns CSTs assigned to the default_teacher_id.     Sign, GET /api/v1/me/classes returns empty list when no CSTs are assigned to     the d (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.23
Nodes (13): login_endpoint(), Register a new client account.      Returns the API key once — store it securely, Authenticate and receive a rotated API key.      Every successful login issues a, Authenticate and receive a rotated API key.      Every successful login issues a, signup_endpoint(), AuthResponse, LoginRequest, SignupRequest (+5 more)

### Community 15 - "Community 15"
Cohesion: 0.17
Nodes (15): add_line_numbers(), clean_topic_title(), _extract_json_from_response(), _extract_topic_text(), format_topic_for_extraction(), Curriculum breakdown service — two-step AI pipeline ported from the Schema repo., Add 'Line: N - ' prefix to each line., Strip 'Topic 1:' style prefix from a section title. (+7 more)

### Community 16 - "Community 16"
Cohesion: 0.36
Nodes (12): admin_headers(), api_key(), headers(), _make_book(), _make_chapter(), _make_school_setup(), test_admin_upsert_chapter_schedule(), test_admin_upsert_is_idempotent() (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.24
Nodes (10): get_teacher_endpoint(), list_teachers_endpoint(), register_teacher_endpoint(), update_teacher_endpoint(), TeacherListResponse, get_teacher(), list_teachers(), register_teacher() (+2 more)

### Community 19 - "Community 19"
Cohesion: 0.38
Nodes (10): api_key(), api_key2(), headers(), _make_academic_year(), _seed_book_and_chapters(), test_create_teacher_class_client_isolation_404(), test_create_teacher_class_happy_path(), test_create_teacher_class_invalid_year_404() (+2 more)

### Community 20 - "Community 20"
Cohesion: 0.31
Nodes (8): _signup(), test_client_isolation_get(), test_client_isolation_list(), test_create_exam_returns_202_pending(), test_create_exam_unknown_grade_422(), test_create_exam_unknown_subject_422(), test_get_exam_by_id(), test_list_exams_shows_own()

### Community 21 - "Community 21"
Cohesion: 0.31
Nodes (8): _signup(), test_client_isolation_get(), test_client_isolation_list(), test_create_lp_returns_202_pending(), test_create_lp_unknown_grade_422(), test_create_lp_unknown_subject_422(), test_get_lp_by_id(), test_list_lps_shows_own()

### Community 22 - "Community 22"
Cohesion: 0.42
Nodes (7): client_headers(), get_books(), get_chapters(), has_topics(), main(), Run AI topic breakdown for all book chapters in Dars.  Calls POST /api/v1/admin/, run_breakdown()

### Community 23 - "Community 23"
Cohesion: 0.39
Nodes (7): fetch_book(), fetch_chapters(), main(), Import books and chapters from taleemabad-core into Dars.  Sources:   ICT    → f, Upsert into dars.books, return the dars book id., upsert_book(), upsert_chapters()

### Community 24 - "Community 24"
Cohesion: 0.29
Nodes (5): lifespan(), _asyncpg_url(), Lightweight migration runner.  Scans supabase/migrations/*.sql in filename order, Convert SQLAlchemy URL scheme to plain asyncpg scheme., run_migrations()

### Community 25 - "Community 25"
Cohesion: 0.29
Nodes (4): WebhookDelivery, deliver_webhook(), test_deliver_webhook_failure_marks_failed_after_max_retries(), test_deliver_webhook_success()

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (8): content_json / answers_json Parallel Arrays, Curriculum Lock (ICT vs Punjab), Curriculum Tree API (GET /api/v1/curriculum), ICT Curriculum, Lesson Plans API, Punjab Curriculum, Student Assessment API, Teacher Assessment API (GET /api/v1/assessments)

### Community 27 - "Community 27"
Cohesion: 0.43
Nodes (8): File/Document Icon (generic file with folded corner and text lines), Globe/World Icon (circle with latitude/longitude grid lines), Dars App Icon (open book with spine, terra dot, dark background), Next.js Wordmark Logo (full NEXT.JS text in black), Vercel Logo (white upward-pointing triangle), Next.js webapp app directory, Next.js webapp public assets directory, Browser Window Icon (rounded rectangle with three traffic-light dots)

### Community 28 - "Community 28"
Cohesion: 0.43
Nodes (6): generate_lp(), get_chapter_slots(), main(), persist_lp(), Generate lesson plans for all slots in a chapter by calling UG LP with topic_tex, Insert LP into lesson_plans, update slot.lesson_plan_id, return lp_id.

### Community 30 - "Community 30"
Cohesion: 0.33
Nodes (6): Curriculum Data Layer (sub-SLOs, topics, join tables), Engine Migration (LP engine absorption), LP Breakdown Module, Phase 1: Curriculum-Driven LP Generation, LP Stub Generation (async per stub), UG_LessonPlan Service

### Community 31 - "Community 31"
Cohesion: 0.4
Nodes (2): BaseSettings, Settings

### Community 34 - "Community 34"
Cohesion: 0.4
Nodes (5): 202 Accepted Async Pattern, Synchronous 60-second Generation Issue, Supabase Connection Pool Saturation Risk, Broad Exception Handling in Generation, Job Queue (arq/pgqueuer)

### Community 35 - "Community 35"
Cohesion: 0.4
Nodes (5): Async Generation Pattern (202 PENDING → READY), Custom Exam Generations API (POST /api/v1/custom-exam-generations), Custom Lesson Plans API (POST /api/v1/custom-lesson-plans), Status Values (PENDING/READY/ERROR), WhatsApp Product (Phase 3.5)

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (2): get_db(), test_db_session_yields_async_session()

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (4): MCP Server Strategic Value, @dars/node SDK Scaffold (unusable), @dars/mcp Server, @dars/node SDK

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (2): EG Integration, UG_EG Exam Generation Service

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (2): Documentation Types & Line Limits, YAML Frontmatter Convention

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Return canonical subject code, raise ValueError if unrecognised.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Return canonical curriculum code, raise ValueError if unrecognised.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Return canonical grade integer, raise ValueError if out of range.

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Raise ValueError if subject is not valid for the given curriculum.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Create a PENDING lesson plan record and return it. Background task fires separat

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Create a PENDING exam generation record and return it. Background task fires sep

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Fetch a single exam generation, always filtering by client_id.

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Return (items, total) for paginated exam generation list, always filtered by cli

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Background task: call EG Assistant, update ExamGeneration record, fire webhook.

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Extract a JSON array from LLM response using two fallback strategies.

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Split MCQs into questions-only and answers-only parallel lists.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Background task: generate MCQs from a lesson plan and update the assessment reco

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Fetch a single custom lesson plan, always filtering by client_id.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Return (items, total) for paginated custom lesson plan list, filtered by client_

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Background task: call LP Assistant, update CustomLessonPlan record.     Uses its

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): Background task: submit to UG_EG v2 async endpoint, poll for result, update reco

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): Extract a JSON array from LLM response using two fallback strategies.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Split MCQs into questions-only and answers-only parallel lists.

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Background task: generate student MCQs from a lesson plan and update the student

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Beads Work Tracking

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): Structured Logging Convention

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): Next.js Agent Rules (AGENTS.md)

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): Webhook DLQ UI

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (1): Daily Make Commands

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): Supabase Environments (dars-dev, dars-prod)

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): API Key Format (dars_ prefix)

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): Migration File Rules

### Community 116 - "Community 116"
Cohesion: 1.0
Nodes (1): metadata_ Field Naming Smell

### Community 117 - "Community 117"
Cohesion: 1.0
Nodes (1): Cursor-Based Pagination (missing)

### Community 118 - "Community 118"
Cohesion: 1.0
Nodes (1): LP Deletion Endpoint (missing)

### Community 119 - "Community 119"
Cohesion: 1.0
Nodes (1): Rate Limiting (missing)

### Community 120 - "Community 120"
Cohesion: 1.0
Nodes (1): API Authentication (X-API-Key)

### Community 121 - "Community 121"
Cohesion: 1.0
Nodes (1): Analytics API (GET /api/v1/analytics)

### Community 122 - "Community 122"
Cohesion: 1.0
Nodes (1): external_id Concept

### Community 123 - "Community 123"
Cohesion: 1.0
Nodes (1): Exam Generation Service

### Community 124 - "Community 124"
Cohesion: 1.0
Nodes (1): Digital Coach Service

## Knowledge Gaps
- **165 isolated node(s):** `Infer auth header from path prefix.`, `Convert /api/v1/lesson-plans to lesson-plans, /admin/clients to admin.`, `Build a sample request body from the OpenAPI schema.`, `Delete all .bru files and subdirectories except environments/.`, `Run AI topic breakdown for all book chapters in Dars.  Calls POST /api/v1/admin/` (+160 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 31`** (5 nodes): `BaseSettings`, `cors_origins_list()`, `effective_core_db_url()`, `Settings`, `config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (4 nodes): `get_db()`, `database.py`, `test_database.py`, `test_db_session_yields_async_session()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (2 nodes): `EG Integration`, `UG_EG Exam Generation Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (2 nodes): `Documentation Types & Line Limits`, `YAML Frontmatter Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Return canonical subject code, raise ValueError if unrecognised.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Return canonical curriculum code, raise ValueError if unrecognised.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Return canonical grade integer, raise ValueError if out of range.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Raise ValueError if subject is not valid for the given curriculum.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Create a PENDING lesson plan record and return it. Background task fires separat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Create a PENDING exam generation record and return it. Background task fires sep`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Fetch a single exam generation, always filtering by client_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Return (items, total) for paginated exam generation list, always filtered by cli`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Background task: call EG Assistant, update ExamGeneration record, fire webhook.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Extract a JSON array from LLM response using two fallback strategies.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Split MCQs into questions-only and answers-only parallel lists.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Background task: generate MCQs from a lesson plan and update the assessment reco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Fetch a single custom lesson plan, always filtering by client_id.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Return (items, total) for paginated custom lesson plan list, filtered by client_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Background task: call LP Assistant, update CustomLessonPlan record.     Uses its`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `Background task: submit to UG_EG v2 async endpoint, poll for result, update reco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `Extract a JSON array from LLM response using two fallback strategies.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Split MCQs into questions-only and answers-only parallel lists.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Background task: generate student MCQs from a lesson plan and update the student`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `Return CORE_DB_URL if set, otherwise build it from the 5-part env vars.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Beads Work Tracking`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `Structured Logging Convention`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `Next.js Agent Rules (AGENTS.md)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `Webhook DLQ UI`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `Daily Make Commands`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `Supabase Environments (dars-dev, dars-prod)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `API Key Format (dars_ prefix)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `Migration File Rules`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 116`** (1 nodes): `metadata_ Field Naming Smell`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 117`** (1 nodes): `Cursor-Based Pagination (missing)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 118`** (1 nodes): `LP Deletion Endpoint (missing)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 119`** (1 nodes): `Rate Limiting (missing)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 120`** (1 nodes): `API Authentication (X-API-Key)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 121`** (1 nodes): `Analytics API (GET /api/v1/analytics)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 122`** (1 nodes): `external_id Concept`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 123`** (1 nodes): `Exam Generation Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 124`** (1 nodes): `Digital Coach Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 0` to `Community 1`, `Community 3`, `Community 36`, `Community 9`, `Community 13`, `Community 25`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `Client` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 13`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `Book` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 7`, `Community 12`, `Community 16`, `Community 19`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 97 inferred relationships involving `Base` (e.g. with `Client` and `WebhookDelivery`) actually correct?**
  _`Base` has 97 INFERRED edges - model-reasoned connections that need verification._
- **Are the 92 inferred relationships involving `Client` (e.g. with `Create a PENDING custom lesson plan record and return it. Background task fires` and `Return (items, total) for paginated lesson plan list.`) actually correct?**
  _`Client` has 92 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `BookChapter` (e.g. with `Admin service for curriculum breakdown.  Orchestrates the two-step AI pipeline (` and `Run the full AI breakdown pipeline for a chapter and persist results.      Steps`) actually correct?**
  _`BookChapter` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Are the 80 inferred relationships involving `Book` (e.g. with `CreateTopicRequest` and `CreateSlotRequest`) actually correct?**
  _`Book` has 80 INFERRED edges - model-reasoned connections that need verification._
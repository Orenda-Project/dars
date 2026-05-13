-- Seed data bank: grades 1-3, subjects English/Urdu/Maths, curriculums NCP + SNC
-- Uses FK schema: curriculum_id, grade_id, subject_id throughout
-- Safe to re-run: uses INSERT ... ON CONFLICT DO NOTHING everywhere

-- ============================================================
-- LOOKUP TABLES
-- ============================================================

INSERT INTO curriculums (code, name) VALUES
  ('NCP', 'National Curriculum of Pakistan'),
  ('SNC', 'Single National Curriculum')
ON CONFLICT (code) DO NOTHING;

INSERT INTO grades (code, display_name) VALUES
  (1, 'Grade 1'),
  (2, 'Grade 2'),
  (3, 'Grade 3')
ON CONFLICT (code) DO NOTHING;

INSERT INTO subjects (code, display_name) VALUES
  ('english', 'English'),
  ('urdu',    'Urdu'),
  ('maths',   'Maths')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- BOOKS
-- ============================================================

INSERT INTO books (curriculum_id, grade_id, subject_id, title, publisher, total_chapters)
SELECT c.id, g.id, s.id, title, publisher, total_chapters
FROM (VALUES
  -- NCP
  ('NCP',1,'english','English for Grade 1',          'National Book Foundation', 6),
  ('NCP',1,'urdu',   'Urdu Qaida Grade 1',            'National Book Foundation', 6),
  ('NCP',1,'maths',  'Mathematics Grade 1',           'National Book Foundation', 6),
  ('NCP',2,'english','English for Grade 2',           'National Book Foundation', 7),
  ('NCP',2,'urdu',   'Urdu Grade 2',                  'National Book Foundation', 7),
  ('NCP',2,'maths',  'Mathematics Grade 2',           'National Book Foundation', 7),
  ('NCP',3,'english','English for Grade 3',           'National Book Foundation', 8),
  ('NCP',3,'urdu',   'Urdu Grade 3',                  'National Book Foundation', 8),
  ('NCP',3,'maths',  'Mathematics Grade 3',           'National Book Foundation', 8),
  -- SNC
  ('SNC',1,'english','English SNC Grade 1',           'Punjab Textbook Board', 6),
  ('SNC',1,'urdu',   'Urdu SNC Grade 1',              'Punjab Textbook Board', 6),
  ('SNC',1,'maths',  'Mathematics SNC Grade 1',       'Punjab Textbook Board', 6),
  ('SNC',2,'english','English SNC Grade 2',           'Punjab Textbook Board', 7),
  ('SNC',2,'urdu',   'Urdu SNC Grade 2',              'Punjab Textbook Board', 7),
  ('SNC',2,'maths',  'Mathematics SNC Grade 2',       'Punjab Textbook Board', 7),
  ('SNC',3,'english','English SNC Grade 3',           'Punjab Textbook Board', 8),
  ('SNC',3,'urdu',   'Urdu SNC Grade 3',              'Punjab Textbook Board', 8),
  ('SNC',3,'maths',  'Mathematics SNC Grade 3',       'Punjab Textbook Board', 8)
) AS v(curr, grade, subj, title, publisher, total_chapters)
JOIN curriculums c ON c.code = v.curr
JOIN grades      g ON g.code = v.grade::int
JOIN subjects    s ON s.code = v.subj
ON CONFLICT DO NOTHING;

-- ============================================================
-- BOOK CHAPTERS
-- ============================================================

-- NCP Grade 1 English
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=1 AND s.code='english')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'My Family'),(2,'My School'),(3,'Animals Around Us'),(4,'Food We Eat'),(5,'Colours and Shapes'),(6,'My Country')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 1 Urdu
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=1 AND s.code='urdu')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'حروف تہجی'),(2,'میرا گھر'),(3,'میرا سکول'),(4,'جانور'),(5,'پھل اور سبزیاں'),(6,'موسم')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 1 Maths
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=1 AND s.code='maths')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Numbers 1-10'),(2,'Numbers 11-20'),(3,'Addition'),(4,'Subtraction'),(5,'Shapes'),(6,'Measurement')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 2 English
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=2 AND s.code='english')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Our Neighbourhood'),(2,'Healthy Habits'),(3,'Transport'),(4,'Seasons'),(5,'Wild Animals'),(6,'Occupations'),(7,'Our Environment')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 2 Urdu
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=2 AND s.code='urdu')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'میرا محلہ'),(2,'صحت اور صفائی'),(3,'ذرائع آمد و رفت'),(4,'موسم'),(5,'جنگلی جانور'),(6,'پیشے'),(7,'ہمارا ماحول')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 2 Maths
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=2 AND s.code='maths')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Numbers to 100'),(2,'Addition to 100'),(3,'Subtraction to 100'),(4,'Multiplication Introduction'),(5,'Fractions'),(6,'Geometry'),(7,'Time and Money')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 3 English
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=3 AND s.code='english')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Reading Comprehension'),(2,'Grammar: Nouns and Pronouns'),(3,'Grammar: Verbs and Tenses'),(4,'Creative Writing'),(5,'Poetry'),(6,'Stories and Fables'),(7,'Pakistan'),(8,'Science and Technology')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 3 Urdu
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=3 AND s.code='urdu')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'نظم'),(2,'کہانی'),(3,'گرامر: اسم'),(4,'گرامر: فعل'),(5,'خط نویسی'),(6,'ہمارا پاکستان'),(7,'مشاہیر'),(8,'تخلیقی تحریر')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- NCP Grade 3 Maths
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='NCP' AND g.code=3 AND s.code='maths')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Numbers to 1000'),(2,'Addition and Subtraction'),(3,'Multiplication Tables'),(4,'Division'),(5,'Fractions'),(6,'Geometry'),(7,'Measurement'),(8,'Data Handling')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 1 English
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=1 AND s.code='english')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Hello World'),(2,'My Home'),(3,'School Life'),(4,'Nature Walk'),(5,'Healthy Me'),(6,'Festivals')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 1 Urdu
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=1 AND s.code='urdu')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'الفاظ سیکھیں'),(2,'میرا گھر'),(3,'سکول'),(4,'فطرت'),(5,'صحت'),(6,'تہوار')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 1 Maths
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=1 AND s.code='maths')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Counting 1-10'),(2,'Counting 11-20'),(3,'Adding Numbers'),(4,'Subtracting Numbers'),(5,'Basic Shapes'),(6,'Comparing Objects')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 2 English
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=2 AND s.code='english')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Community Helpers'),(2,'Good Habits'),(3,'How We Travel'),(4,'Four Seasons'),(5,'Safari Animals'),(6,'Jobs and Work'),(7,'Green Earth')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 2 Urdu
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=2 AND s.code='urdu')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'مددگار لوگ'),(2,'اچھی عادتیں'),(3,'سفر'),(4,'موسم'),(5,'جانور'),(6,'پیشے'),(7,'ماحول کی حفاظت')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 2 Maths
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=2 AND s.code='maths')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Place Value'),(2,'Addition'),(3,'Subtraction'),(4,'Introduction to Multiplication'),(5,'Half and Quarter'),(6,'2D and 3D Shapes'),(7,'Clocks and Calendar')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 3 English
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=3 AND s.code='english')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Reading Skills'),(2,'Nouns and Pronouns'),(3,'Verbs and Tenses'),(4,'Writing Skills'),(5,'Poems'),(6,'Short Stories'),(7,'Our Beautiful Pakistan'),(8,'Technology Today')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 3 Urdu
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=3 AND s.code='urdu')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'نثر پارہ'),(2,'نظم'),(3,'اسم اور ضمیر'),(4,'فعل'),(5,'خط'),(6,'پاکستان'),(7,'عظیم لوگ'),(8,'تحریری مشق')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- SNC Grade 3 Maths
WITH b AS (SELECT id FROM books JOIN curriculums c ON c.id=curriculum_id JOIN grades g ON g.id=grade_id JOIN subjects s ON s.id=subject_id WHERE c.code='SNC' AND g.code=3 AND s.code='maths')
INSERT INTO book_chapters (book_id, chapter_number, title) SELECT b.id, n, t FROM b, (VALUES
  (1,'Large Numbers'),(2,'Addition and Subtraction'),(3,'Multiplication'),(4,'Division'),(5,'Fractions and Decimals'),(6,'Geometry and Shapes'),(7,'Units of Measurement'),(8,'Graphs and Data')
) AS v(n,t) ON CONFLICT DO NOTHING;

-- ============================================================
-- TOPICS (3 per chapter, generic for all books)
-- ============================================================

INSERT INTO topics (chapter_id, topic_number, title)
SELECT bc.id, v.n, 'Topic ' || v.n || ': ' || bc.title || ' — Part ' || v.n
FROM book_chapters bc
JOIN books bk ON bk.id = bc.book_id
JOIN curriculums c ON c.id = bk.curriculum_id
JOIN grades g ON g.id = bk.grade_id
JOIN subjects s ON s.id = bk.subject_id
CROSS JOIN (VALUES (1),(2),(3)) AS v(n)
WHERE c.code IN ('NCP','SNC')
  AND g.code IN (1,2,3)
  AND s.code IN ('english','urdu','maths')
ON CONFLICT DO NOTHING;

-- ============================================================
-- CURRICULUM CHAPTER SCHEDULE (suggested_teaching_days per chapter)
-- ============================================================

INSERT INTO curriculum_chapter_schedule (curriculum_id, book_id, chapter_id, suggested_teaching_days, suggested_position)
SELECT bk.curriculum_id, bk.id, bc.id, 5, bc.chapter_number
FROM book_chapters bc
JOIN books bk ON bk.id = bc.book_id
JOIN curriculums c ON c.id = bk.curriculum_id
JOIN grades g ON g.id = bk.grade_id
JOIN subjects s ON s.id = bk.subject_id
WHERE c.code IN ('NCP','SNC')
  AND g.code IN (1,2,3)
  AND s.code IN ('english','urdu','maths')
ON CONFLICT (curriculum_id, chapter_id) DO NOTHING;

-- ============================================================
-- SLOs
-- ============================================================

INSERT INTO slos (curriculum_id, grade_id, subject_id, code, description)
SELECT c.id, g.id, s.id, v.code, v.description
FROM (VALUES
  -- NCP Grade 1 English
  ('NCP',1,'english','E1.1.1','Student can identify and name family members in English'),
  ('NCP',1,'english','E1.1.2','Student can use simple sentences to describe their family'),
  ('NCP',1,'english','E1.2.1','Student can name common classroom objects'),
  ('NCP',1,'english','E1.2.2','Student can follow simple classroom instructions'),
  ('NCP',1,'english','E1.3.1','Student can identify and name common animals'),
  ('NCP',1,'english','E1.3.2','Student can describe animals using simple adjectives'),
  ('NCP',1,'english','E1.4.1','Student can name common fruits and vegetables'),
  ('NCP',1,'english','E1.4.2','Student can identify healthy and unhealthy foods'),
  ('NCP',1,'english','E1.5.1','Student can identify and name basic colours'),
  ('NCP',1,'english','E1.5.2','Student can identify basic 2D shapes'),
  ('NCP',1,'english','E1.6.1','Student can name national symbols of Pakistan'),
  ('NCP',1,'english','E1.6.2','Student can identify the Pakistani flag and its colours'),
  -- NCP Grade 1 Urdu
  ('NCP',1,'urdu','U1.1.1','طالب علم حروف تہجی پہچان سکتا ہے'),
  ('NCP',1,'urdu','U1.1.2','طالب علم حروف تہجی لکھ سکتا ہے'),
  ('NCP',1,'urdu','U1.2.1','طالب علم گھر کے افراد کے نام بتا سکتا ہے'),
  ('NCP',1,'urdu','U1.3.1','طالب علم سکول کی چیزوں کے نام جانتا ہے'),
  ('NCP',1,'urdu','U1.4.1','طالب علم جانوروں کے نام اردو میں بتا سکتا ہے'),
  ('NCP',1,'urdu','U1.5.1','طالب علم پھلوں اور سبزیوں کے نام جانتا ہے'),
  ('NCP',1,'urdu','U1.6.1','طالب علم موسموں کے بارے میں بات کر سکتا ہے'),
  -- NCP Grade 1 Maths
  ('NCP',1,'maths','M1.1.1','Student can count objects from 1 to 10'),
  ('NCP',1,'maths','M1.1.2','Student can write numbers 1 to 10'),
  ('NCP',1,'maths','M1.2.1','Student can count objects from 11 to 20'),
  ('NCP',1,'maths','M1.2.2','Student can order numbers from 1 to 20'),
  ('NCP',1,'maths','M1.3.1','Student can add two single-digit numbers'),
  ('NCP',1,'maths','M1.3.2','Student can solve simple addition word problems'),
  ('NCP',1,'maths','M1.4.1','Student can subtract single-digit numbers'),
  ('NCP',1,'maths','M1.4.2','Student can solve simple subtraction word problems'),
  ('NCP',1,'maths','M1.5.1','Student can identify circle, square, triangle, and rectangle'),
  ('NCP',1,'maths','M1.5.2','Student can match shapes to real-life objects'),
  ('NCP',1,'maths','M1.6.1','Student can compare lengths using long and short'),
  ('NCP',1,'maths','M1.6.2','Student can compare weights using heavy and light'),
  -- NCP Grade 2 English
  ('NCP',2,'english','E2.1.1','Student can describe their neighbourhood using simple sentences'),
  ('NCP',2,'english','E2.1.2','Student can identify community helpers and their roles'),
  ('NCP',2,'english','E2.2.1','Student can talk about healthy habits'),
  ('NCP',2,'english','E2.3.1','Student can name different modes of transport'),
  ('NCP',2,'english','E2.4.1','Student can describe the four seasons'),
  ('NCP',2,'english','E2.5.1','Student can name and describe wild animals'),
  ('NCP',2,'english','E2.6.1','Student can name common occupations'),
  ('NCP',2,'english','E2.7.1','Student can identify ways to protect the environment'),
  -- NCP Grade 2 Urdu
  ('NCP',2,'urdu','U2.1.1','طالب علم اپنے محلے کے بارے میں بتا سکتا ہے'),
  ('NCP',2,'urdu','U2.2.1','طالب علم صحت اور صفائی کی اہمیت جانتا ہے'),
  ('NCP',2,'urdu','U2.3.1','طالب علم ذرائع آمد و رفت کے نام جانتا ہے'),
  ('NCP',2,'urdu','U2.4.1','طالب علم موسموں کی تبدیلی بیان کر سکتا ہے'),
  ('NCP',2,'urdu','U2.5.1','طالب علم جنگلی جانوروں کے بارے میں بتا سکتا ہے'),
  ('NCP',2,'urdu','U2.6.1','طالب علم مختلف پیشوں کے نام جانتا ہے'),
  ('NCP',2,'urdu','U2.7.1','طالب علم ماحول کی حفاظت کی اہمیت سمجھتا ہے'),
  -- NCP Grade 2 Maths
  ('NCP',2,'maths','M2.1.1','Student can read and write numbers up to 100'),
  ('NCP',2,'maths','M2.1.2','Student can identify place value of tens and ones'),
  ('NCP',2,'maths','M2.2.1','Student can add two-digit numbers without carrying'),
  ('NCP',2,'maths','M2.2.2','Student can add two-digit numbers with carrying'),
  ('NCP',2,'maths','M2.3.1','Student can subtract two-digit numbers without borrowing'),
  ('NCP',2,'maths','M2.3.2','Student can subtract two-digit numbers with borrowing'),
  ('NCP',2,'maths','M2.4.1','Student can understand multiplication as repeated addition'),
  ('NCP',2,'maths','M2.5.1','Student can identify half and quarter of a shape'),
  ('NCP',2,'maths','M2.6.1','Student can identify 2D and 3D shapes'),
  ('NCP',2,'maths','M2.7.1','Student can read a clock to the hour and half hour'),
  -- NCP Grade 3 English
  ('NCP',3,'english','E3.1.1','Student can read a passage and answer comprehension questions'),
  ('NCP',3,'english','E3.1.2','Student can identify the main idea of a paragraph'),
  ('NCP',3,'english','E3.2.1','Student can identify nouns and pronouns in sentences'),
  ('NCP',3,'english','E3.3.1','Student can use past, present, and future tenses correctly'),
  ('NCP',3,'english','E3.4.1','Student can write a short paragraph on a given topic'),
  ('NCP',3,'english','E3.5.1','Student can recite a poem with expression'),
  ('NCP',3,'english','E3.6.1','Student can retell a story in their own words'),
  ('NCP',3,'english','E3.7.1','Student can describe key facts about Pakistan'),
  -- NCP Grade 3 Urdu
  ('NCP',3,'urdu','U3.1.1','طالب علم نظم پڑھ کر سمجھ سکتا ہے'),
  ('NCP',3,'urdu','U3.2.1','طالب علم کہانی کا خلاصہ بیان کر سکتا ہے'),
  ('NCP',3,'urdu','U3.3.1','طالب علم اسم اور ضمیر کی پہچان کر سکتا ہے'),
  ('NCP',3,'urdu','U3.4.1','طالب علم فعل کے استعمال سے واقف ہے'),
  ('NCP',3,'urdu','U3.5.1','طالب علم سادہ خط لکھ سکتا ہے'),
  ('NCP',3,'urdu','U3.6.1','طالب علم پاکستان کے بارے میں معلومات رکھتا ہے'),
  ('NCP',3,'urdu','U3.7.1','طالب علم مشاہیر کی زندگیوں کے بارے میں جانتا ہے'),
  ('NCP',3,'urdu','U3.8.1','طالب علم تخلیقی تحریر لکھ سکتا ہے'),
  -- NCP Grade 3 Maths
  ('NCP',3,'maths','M3.1.1','Student can read and write numbers up to 1000'),
  ('NCP',3,'maths','M3.1.2','Student can identify place value of hundreds, tens, and ones'),
  ('NCP',3,'maths','M3.2.1','Student can add three-digit numbers'),
  ('NCP',3,'maths','M3.2.2','Student can subtract three-digit numbers'),
  ('NCP',3,'maths','M3.3.1','Student can recall multiplication tables up to 10'),
  ('NCP',3,'maths','M3.4.1','Student can perform simple division'),
  ('NCP',3,'maths','M3.5.1','Student can identify and compare fractions'),
  ('NCP',3,'maths','M3.6.1','Student can identify properties of 2D and 3D shapes'),
  ('NCP',3,'maths','M3.7.1','Student can measure length, weight, and capacity'),
  ('NCP',3,'maths','M3.8.1','Student can read and interpret a simple bar graph')
) AS v(curr, grade, subj, code, description)
JOIN curriculums c ON c.code = v.curr
JOIN grades      g ON g.code = v.grade::int
JOIN subjects    s ON s.code = v.subj
ON CONFLICT DO NOTHING;

-- Mirror NCP SLOs to SNC (replace NCP prefix in code with SNC)
INSERT INTO slos (curriculum_id, grade_id, subject_id, code, description)
SELECT
  (SELECT id FROM curriculums WHERE code = 'SNC'),
  grade_id,
  subject_id,
  REPLACE(slos.code, 'NCP', 'SNC'),
  description
FROM slos
JOIN curriculums c ON c.id = slos.curriculum_id
WHERE c.code = 'NCP'
ON CONFLICT DO NOTHING;

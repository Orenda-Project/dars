CREATE TABLE IF NOT EXISTS grades (
  code         INT PRIMARY KEY,
  display_name TEXT NOT NULL
);

INSERT INTO grades (code, display_name) VALUES
  (1, 'Grade 1'),
  (2, 'Grade 2'),
  (3, 'Grade 3'),
  (4, 'Grade 4'),
  (5, 'Grade 5')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS subjects (
  code         TEXT PRIMARY KEY,
  display_name TEXT NOT NULL
);

INSERT INTO subjects (code, display_name) VALUES
  ('Eng',      'English'),
  ('Maths',    'Mathematics'),
  ('Urdu',     'Urdu'),
  ('Science',  'Science'),
  ('GK',       'General Knowledge'),
  ('Islamiat', 'Islamiat'),
  ('SST',      'Social Studies')
ON CONFLICT (code) DO NOTHING;

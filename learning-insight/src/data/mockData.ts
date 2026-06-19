export interface DailySession {
  userid: number;
  activity_date: string; // YYYY-MM-DD
  day_of_week: number; // 0=Pzt, 6=Paz
  session_count: number;
  total_minutes: number;
  page_views: number;
}

export interface UserStats {
  userid: number;
  focus_score: number; // 0-100
  focus_score_delta_pct: number;
  avg_grade: number; // 0-100
  avg_grade_delta: number; // Fixed 0.0
  study_streak_days: number;
  streak_delta: number; // 0/1
  late_assignment_count: number;
  late_assignment_delta: number; // Fixed 0
  total_courses_active: number;
  total_study_minutes: number;
  avg_session_minutes: number;
  sessions_per_active_day: number;
  last_active_date: string; // YYYY-MM-DD
  computed_at: string; // datetime
}

export interface CourseProgress {
  userid: number;
  courseid: number;
  course_fullname: string;
  course_shortname: string;
  course_visible: number; // 0/1
  enrollment_status: number; // 0=aktif, 1=pasif
  total_visible_modules: number;
  completed_modules: number;
  completion_pct: number; // 0-100
  avg_grade: number; // 0-100
  next_expected_date: string | null;
  last_activity_date: string;
  computed_at: string;
}

export interface ModuleStatus {
  userid: number;
  courseid: number;
  cmid: number;
  module_type: 'assign' | 'quiz' | 'resource' | 'forum' | 'page' | 'book' | string;
  display_name: string;
  section_order: number;
  is_visible: boolean;
  is_available: boolean;
  completion_required: number; // 0=yok, 1=manuel, 2=otomatik
  is_completed: boolean;
  completion_action: string | null; // e.g. "submit", "view"
  completion_time: number | null; // Unix timestamp
  first_view_time: number | null; // Unix timestamp
  view_to_complete_hours: number | null;
  expected_date: string | null; // YYYY-MM-DD
  added_date: string | null; // YYYY-MM-DD
}

export interface CourseAnalytics {
  userid: number;
  courseid: number;
  most_common_module_type: string;
  assign_total: number;
  assign_completed: number;
  assign_completion_rate: number;
  quiz_total: number;
  quiz_completed: number;
  quiz_completion_rate: number;
  resource_total: number;
  resource_viewed: number;
  resource_view_rate: number;
  forum_total: number;
  forum_interactions: number;
  forum_interaction_rate: number;
  page_total: number;
  page_viewed: number;
  page_view_rate: number;
  avg_daily_minutes: number;
  total_active_days: number;
  total_events: number;
  last_activity_date: string;
}

export interface ActivityHeatmap {
  userid: number;
  weekday: number; // 0=Pazartesi, 6=Pazar (Wait, original SQL: 0=Pazartesi, 6=Pazar)
  hour: number; // 0-23
  event_count: number;
  session_starts: number;
}

export interface UpcomingEvent {
  userid: number;
  courseid: number;
  cmid: number;
  module_type: string;
  display_name: string;
  course_name: string;
  course_short: string;
  event_date: string; // YYYY-MM-DD
  timestart: number; // Unix timestamp UTC midnight
  days_until: number; // Positive = remaining, negative = overdue
  is_overdue: boolean;
  is_completed: boolean;
}

export interface StudentProfile {
  id: number;
  name: string;
  firstName: string;
  photo: string;
  program: string;
}

// Concrete dataset adhering to standard specs
export const studentProfile: StudentProfile = {
  id: 1042,
  name: 'Büşra Kirencioğlu',
  firstName: 'Büşra',
  photo: 'https://cdn3.pixelcut.app/7/20/uncrop_hero_bdf08a8ca6.jpg',
  program: 'Bilgisayar Mühendisliği · 3. Sınıf',
};

// dash_01_daily_sessions.csv
export const dash_01_daily_sessions: DailySession[] = [
  { userid: 1042, activity_date: '2026-06-11', day_of_week: 3, session_count: 2, total_minutes: 45.5, page_views: 18 },
  { userid: 1042, activity_date: '2026-06-12', day_of_week: 4, session_count: 3, total_minutes: 60.0, page_views: 24 },
  { userid: 1042, activity_date: '2026-06-13', day_of_week: 5, session_count: 1, total_minutes: 25.2, page_views: 8 },
  { userid: 1042, activity_date: '2026-06-14', day_of_week: 6, session_count: 0, total_minutes: 0.0, page_views: 0 },
  { userid: 1042, activity_date: '2026-06-15', day_of_week: 0, session_count: 4, total_minutes: 120.4, page_views: 45 },
  { userid: 1042, activity_date: '2026-06-16', day_of_week: 1, session_count: 3, total_minutes: 85.0, page_views: 32 },
  { userid: 1042, activity_date: '2026-06-17', day_of_week: 2, session_count: 2, total_minutes: 50.0, page_views: 19 },
];

// Term data for GPA trend
export const gradeTrend = {
  terms: ['2024 Güz', '2025 Bahar', '2025 Güz', '2026 Bahar'],
  gpa: [2.84, 3.05, 3.18, 3.31],
};

// dash_02_user_stats.csv
export const dash_02_user_stats: UserStats = {
  userid: 1042,
  focus_score: 68.0,
  focus_score_delta_pct: 12.3,
  avg_grade: 82.5,
  avg_grade_delta: 0.0,
  study_streak_days: 6,
  streak_delta: 1,
  late_assignment_count: 2,
  late_assignment_delta: 0,
  total_courses_active: 4,
  total_study_minutes: 386.1,
  avg_session_minutes: 25.74, // total_minutes / total_sessions
  sessions_per_active_day: 2.5,
  last_active_date: '2026-06-17',
  computed_at: '2026-06-17 04:00:00',
};

// Instructor names maps
export const courseInstructors: Record<number, string> = {
  101: 'Prof. M. Demir',
  110: 'L. Brown',
  201: 'Dr. A. Yılmaz',
  202: 'Dr. E. Şahin',
  250: 'Dr. S. Kaya',
  321: 'Dr. S. Kaya',
};

// Color maps
export const courseColors: Record<number, string> = {
  101: 'var(--cat-emerald)',
  110: 'var(--cat-sky)',
  201: 'var(--cat-blue)',
  202: 'var(--cat-purple)',
  250: 'var(--cat-orange)',
  321: 'var(--cat-red)',
};

// Credits map
export const courseCredits: Record<number, number> = {
  101: 5,
  110: 3,
  201: 6,
  202: 5,
  250: 6,
  321: 6,
};

// dash_03_course_progress.csv
export const dash_03_course_progress: CourseProgress[] = [
  {
    userid: 1042,
    courseid: 201,
    course_fullname: 'Calculus I',
    course_shortname: 'MATH201',
    course_visible: 1,
    enrollment_status: 0,
    total_visible_modules: 25,
    completed_modules: 17,
    completion_pct: 68.0,
    avg_grade: 84.0,
    next_expected_date: '2026-06-20',
    last_activity_date: '2026-06-17',
    computed_at: '2026-06-17 04:00:00',
  },
  {
    userid: 1042,
    courseid: 101,
    course_fullname: 'Fizik 101',
    course_shortname: 'PHYS101',
    course_visible: 1,
    enrollment_status: 0,
    total_visible_modules: 25,
    completed_modules: 23,
    completion_pct: 92.0,
    avg_grade: 92.0,
    next_expected_date: '2026-06-22',
    last_activity_date: '2026-06-16',
    computed_at: '2026-06-17 04:00:00',
  },
  {
    userid: 1042,
    courseid: 250,
    course_fullname: 'Veri Yapıları',
    course_shortname: 'CMPE250',
    course_visible: 1,
    enrollment_status: 0,
    total_visible_modules: 20,
    completed_modules: 9,
    completion_pct: 45.0,
    avg_grade: 71.0,
    next_expected_date: '2026-06-19',
    last_activity_date: '2026-06-15',
    computed_at: '2026-06-17 04:00:00',
  },
  {
    userid: 1042,
    courseid: 202,
    course_fullname: 'Olasılık',
    course_shortname: 'MATH202',
    course_visible: 1,
    enrollment_status: 0,
    total_visible_modules: 20,
    completed_modules: 16,
    completion_pct: 80.0,
    avg_grade: 78.0,
    next_expected_date: '2026-06-28',
    last_activity_date: '2026-06-17',
    computed_at: '2026-06-17 04:00:00',
  },
  {
    userid: 1042,
    courseid: 110,
    course_fullname: 'Akademik İngilizce',
    course_shortname: 'HUM101',
    course_visible: 1,
    enrollment_status: 0,
    total_visible_modules: 15,
    completed_modules: 15,
    completion_pct: 100.0,
    avg_grade: 88.0,
    next_expected_date: null,
    last_activity_date: '2026-06-10',
    computed_at: '2026-06-17 04:00:00',
  },
  {
    userid: 1042,
    courseid: 321,
    course_fullname: 'Veritabanı',
    course_shortname: 'CMPE321',
    course_visible: 1,
    enrollment_status: 1,
    total_visible_modules: 16,
    completed_modules: 2,
    completion_pct: 12.5,
    avg_grade: 0.0,
    next_expected_date: null,
    last_activity_date: '2026-05-15',
    computed_at: '2026-06-17 04:00:00',
  },
];

// dash_04_module_status.csv
export const dash_04_module_status: ModuleStatus[] = [
  // Calculus I (201)
  { userid: 1042, courseid: 201, cmid: 20101, module_type: 'quiz', display_name: 'Quiz 1', section_order: 1, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1760083200, first_view_time: 1760079600, view_to_complete_hours: 1.0, expected_date: '2025-10-14', added_date: '2025-09-15' },
  { userid: 1042, courseid: 201, cmid: 20102, module_type: 'quiz', display_name: 'Vize', section_order: 2, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1762588800, first_view_time: 1762578000, view_to_complete_hours: 3.0, expected_date: '2025-11-12', added_date: '2025-09-15' },
  { userid: 1042, courseid: 201, cmid: 20103, module_type: 'assign', display_name: 'Ödev 2', section_order: 3, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1763971200, first_view_time: 1763913600, view_to_complete_hours: 16.0, expected_date: '2025-11-28', added_date: '2025-10-01' },
  { userid: 1042, courseid: 201, cmid: 20104, module_type: 'quiz', display_name: 'Quiz 4', section_order: 4, is_visible: true, is_available: true, completion_required: 2, is_completed: false, completion_action: null, completion_time: null, first_view_time: 1781442000, view_to_complete_hours: null, expected_date: '2026-06-24', added_date: '2026-05-15' },
  { userid: 1042, courseid: 201, cmid: 20105, module_type: 'resource', display_name: 'Ders Notu - Modül 1', section_order: 1, is_visible: true, is_available: true, completion_required: 1, is_completed: true, completion_action: 'view', completion_time: 1760000000, first_view_time: 1760000000, view_to_complete_hours: 0.0, expected_date: null, added_date: '2025-09-15' },
  
  // Fizik 101 (101)
  { userid: 1042, courseid: 101, cmid: 10101, module_type: 'assign', display_name: 'Lab 3', section_order: 1, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1761984000, first_view_time: 1761948000, view_to_complete_hours: 10.0, expected_date: '2025-11-05', added_date: '2025-09-15' },
  { userid: 1042, courseid: 101, cmid: 10102, module_type: 'quiz', display_name: 'Vize', section_order: 2, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1762848000, first_view_time: 1762837200, view_to_complete_hours: 3.0, expected_date: '2025-11-15', added_date: '2025-09-15' },
  { userid: 1042, courseid: 101, cmid: 10103, module_type: 'assign', display_name: 'Lab Raporu', section_order: 3, is_visible: true, is_available: true, completion_required: 2, is_completed: false, completion_action: null, completion_time: null, first_view_time: null, view_to_complete_hours: null, expected_date: '2026-06-26', added_date: '2026-05-20' },
  
  // Veri Yapıları (250)
  { userid: 1042, courseid: 250, cmid: 25001, module_type: 'quiz', display_name: 'Quiz 3', section_order: 1, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1764316800, first_view_time: 1764313200, view_to_complete_hours: 1.0, expected_date: '2025-12-02', added_date: '2025-09-15' },
  { userid: 1042, courseid: 250, cmid: 25002, module_type: 'assign', display_name: 'Proje 1', section_order: 2, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1764921600, first_view_time: 1764748800, view_to_complete_hours: 48.0, expected_date: '2025-12-09', added_date: '2025-10-10' },
  { userid: 1042, courseid: 250, cmid: 25003, module_type: 'assign', display_name: 'Ödev 3', section_order: 3, is_visible: true, is_available: true, completion_required: 2, is_completed: false, completion_action: null, completion_time: null, first_view_time: null, view_to_complete_hours: null, expected_date: '2026-06-15', added_date: '2026-05-10' }, // Overdue!

  // Olasılık (202)
  { userid: 1042, courseid: 202, cmid: 20201, module_type: 'quiz', display_name: 'Quiz 2', section_order: 1, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1763280000, first_view_time: 1763276400, view_to_complete_hours: 1.0, expected_date: '2025-11-20', added_date: '2025-09-15' },
  { userid: 1042, courseid: 202, cmid: 20202, module_type: 'assign', display_name: 'Ödev 4', section_order: 2, is_visible: true, is_available: true, completion_required: 2, is_completed: true, completion_action: 'submit', completion_time: 1764489600, first_view_time: 1764403200, view_to_complete_hours: 24.0, expected_date: '2025-12-04', added_date: '2025-10-05' },
  { userid: 1042, courseid: 202, cmid: 20203, module_type: 'quiz', display_name: 'Vize', section_order: 3, is_visible: true, is_available: true, completion_required: 2, is_completed: false, completion_action: null, completion_time: null, first_view_time: null, view_to_complete_hours: null, expected_date: '2026-06-12', added_date: '2026-05-10' }, // Overdue!
  { userid: 1042, courseid: 202, cmid: 20204, module_type: 'forum', display_name: 'Ders Forumu', section_order: 1, is_visible: true, is_available: true, completion_required: 0, is_completed: true, completion_action: 'view', completion_time: 1781200000, first_view_time: 1781200000, view_to_complete_hours: null, expected_date: null, added_date: '2026-05-15' },
];

// For display in Competencies radar
export const competencies = [
  { name: 'Problem Çözme', value: 82, framework: 'Mühendislik Yetkinlikleri' },
  { name: 'Analitik Düşünme', value: 74, framework: 'Mühendislik Yetkinlikleri' },
  { name: 'Programlama', value: 88, framework: 'Bilgisayar Bilimleri' },
  { name: 'Matematik', value: 79, framework: 'Temel Bilimler' },
  { name: 'İletişim', value: 65, framework: 'Genel Beceriler' },
  { name: 'Takım Çalışması', value: 71, framework: 'Genel Beceriler' },
];

// Activity type distribution
export const activityBreakdown = [
  { label: 'Okuma', moodle: 'resource/page', value: 30, color: 'var(--cat-blue)' },
  { label: 'İzleme', moodle: 'url/scorm', value: 22, color: 'var(--brand-sky)' },
  { label: 'Ödev', moodle: 'assign', value: 24, color: 'var(--brand-navy)' },
  { label: 'Forum', moodle: 'forum', value: 12, color: 'var(--cat-sky)' },
  { label: 'Sınav', moodle: 'quiz', value: 12, color: 'var(--cat-purple)' },
];

// dash_05_course_analytics.csv
export const dash_05_course_analytics: CourseAnalytics[] = [
  {
    userid: 1042,
    courseid: 201,
    most_common_module_type: 'quiz',
    assign_total: 6,
    assign_completed: 4,
    assign_completion_rate: 66.6,
    quiz_total: 8,
    quiz_completed: 6,
    quiz_completion_rate: 75.0,
    resource_total: 10,
    resource_viewed: 7,
    resource_view_rate: 70.0,
    forum_total: 1,
    forum_interactions: 0,
    forum_interaction_rate: 0.0,
    page_total: 0,
    page_viewed: 0,
    page_view_rate: 0.0,
    avg_daily_minutes: 18.5,
    total_active_days: 14,
    total_events: 124,
    last_activity_date: '2026-06-17',
  },
  {
    userid: 1042,
    courseid: 101,
    most_common_module_type: 'assign',
    assign_total: 8,
    assign_completed: 8,
    assign_completion_rate: 100.0,
    quiz_total: 4,
    quiz_completed: 3,
    quiz_completion_rate: 75.0,
    resource_total: 12,
    resource_viewed: 11,
    resource_view_rate: 91.6,
    forum_total: 1,
    forum_interactions: 1,
    forum_interaction_rate: 100.0,
    page_total: 0,
    page_viewed: 0,
    page_view_rate: 0.0,
    avg_daily_minutes: 24.2,
    total_active_days: 18,
    total_events: 180,
    last_activity_date: '2026-06-16',
  },
  {
    userid: 1042,
    courseid: 250,
    most_common_module_type: 'assign',
    assign_total: 5,
    assign_completed: 2,
    assign_completion_rate: 40.0,
    quiz_total: 5,
    quiz_completed: 2,
    quiz_completion_rate: 40.0,
    resource_total: 8,
    resource_viewed: 5,
    resource_view_rate: 62.5,
    forum_total: 2,
    forum_interactions: 0,
    forum_interaction_rate: 0.0,
    page_total: 0,
    page_viewed: 0,
    page_view_rate: 0.0,
    avg_daily_minutes: 12.0,
    total_active_days: 8,
    total_events: 68,
    last_activity_date: '2026-06-15',
  },
  {
    userid: 1042,
    courseid: 202,
    most_common_module_type: 'quiz',
    assign_total: 4,
    assign_completed: 3,
    assign_completion_rate: 75.0,
    quiz_total: 6,
    quiz_completed: 5,
    quiz_completion_rate: 83.3,
    resource_total: 8,
    resource_viewed: 7,
    resource_view_rate: 87.5,
    forum_total: 2,
    forum_interactions: 1,
    forum_interaction_rate: 50.0,
    page_total: 0,
    page_viewed: 0,
    page_view_rate: 0.0,
    avg_daily_minutes: 15.6,
    total_active_days: 12,
    total_events: 102,
    last_activity_date: '2026-06-17',
  },
];

// generate dash_06_activity_heatmap.csv
// ~168 rows (7 days * 24 hours)
export const dash_06_activity_heatmap: ActivityHeatmap[] = (() => {
  const list: ActivityHeatmap[] = [];
  // Peak study times: 8 AM - 11 AM (weekday 0-4), 3 PM - 5 PM
  for (let weekday = 0; weekday < 7; weekday++) {
    for (let hour = 0; hour < 24; hour++) {
      let count = 0;
      let starts = 0;
      // weekdays
      if (weekday < 5) {
        if (hour >= 8 && hour <= 11) {
          count = Math.floor(Math.random() * 15) + 8;
          starts = Math.random() > 0.5 ? 1 : 0;
        } else if (hour >= 14 && hour <= 17) {
          count = Math.floor(Math.random() * 10) + 4;
          starts = Math.random() > 0.7 ? 1 : 0;
        } else if (hour >= 19 && hour <= 22) {
          count = Math.floor(Math.random() * 6) + 2;
          starts = Math.random() > 0.8 ? 1 : 0;
        }
      } else {
        // weekends (lower activity)
        if (hour >= 10 && hour <= 15) {
          count = Math.floor(Math.random() * 8) + 2;
          starts = Math.random() > 0.6 ? 1 : 0;
        }
      }
      list.push({
        userid: 1042,
        weekday,
        hour,
        event_count: count,
        session_starts: starts,
      });
    }
  }
  return list;
})();

// dash_07_upcoming_events.csv
export const dash_07_upcoming_events: UpcomingEvent[] = [
  { userid: 1042, courseid: 250, cmid: 25003, module_type: 'assign', display_name: 'Ödev 3', course_name: 'Veri Yapıları', course_short: 'CMPE250', event_date: '2026-06-15', timestart: 1781481600, days_until: -2, is_overdue: true, is_completed: false },
  { userid: 1042, courseid: 202, cmid: 20203, module_type: 'quiz', display_name: 'Vize', course_name: 'Olasılık', course_short: 'MATH202', event_date: '2026-06-12', timestart: 1781222400, days_until: -5, is_overdue: true, is_completed: false },
  { userid: 1042, courseid: 201, cmid: 20104, module_type: 'quiz', display_name: 'Quiz 4', course_name: 'Calculus I', course_short: 'MATH201', event_date: '2026-06-20', timestart: 1781913600, days_until: 3, is_overdue: false, is_completed: false },
  { userid: 1042, courseid: 101, cmid: 10103, module_type: 'assign', display_name: 'Lab Raporu', course_name: 'Fizik 101', course_short: 'PHYS101', event_date: '2026-06-22', timestart: 1782086400, days_until: 5, is_overdue: false, is_completed: false },
  { userid: 1042, courseid: 202, cmid: 20205, module_type: 'quiz', display_name: 'Final', course_name: 'Olasılık', course_short: 'MATH202', event_date: '2026-06-28', timestart: 1782604800, days_until: 11, is_overdue: false, is_completed: false },
];

export const insights = [
  { icon: 'schedule', title: 'En verimli saatlerin 08:00–11:00', body: 'Sabah çalışmaların akşama göre %23 daha yüksek puan getiriyor.', tone: 'primary' },
  { icon: 'trending_down', title: 'Veri Yapıları’nda düşüş var', body: 'Son iki quizde ortalaman %12 geriledi — Modül 3’ü tekrar et.', tone: 'red' },
  { icon: 'local_fire_department', title: '6 günlük çalışma serisi', body: 'Seriyi sürdürmek için bugün en az 30 dk çalış.', tone: 'gold' },
];

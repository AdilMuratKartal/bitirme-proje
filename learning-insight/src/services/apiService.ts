import { auth } from '../firebaseConfig';
import * as mock from '../data/mockData';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://learning-insight-api.onrender.com';

// Utility to sleep between retries
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export interface ApiResponse<T> {
  data: T;
  fallback: boolean;
}

// Fetch helper with retry logic (up to 3 total attempts)
async function fetchWithRetry<T>(endpoint: string, mockFallback: T): Promise<ApiResponse<T>> {
  let attempts = 0;
  const maxAttempts = 3;

  while (attempts < maxAttempts) {
    attempts++;
    try {
      const token = await auth.currentUser?.getIdToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'GET',
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        return { data, fallback: false };
      } else {
        console.warn(`API attempt ${attempts} failed for ${endpoint}: Status ${response.status}`);
      }
    } catch (error) {
      console.warn(`API attempt ${attempts} threw error for ${endpoint}:`, error);
    }

    // Wait before retrying (e.g., 800ms)
    if (attempts < maxAttempts) {
      await sleep(800);
    }
  }

  // Fallback to mock data if all 3 attempts fail
  console.error(`All ${maxAttempts} attempts failed for ${endpoint}. Falling back to mock data.`);
  return { data: mockFallback, fallback: true };
}

// Main API calls
export const apiService = {
  // 1. GET /api/student/me/home
  getStudentHome: async (_uid: string) => {
    const fallbackData = {
      user: mock.studentProfile,
      courses: mock.dash_03_course_progress.map(c => ({
        ...c,
        instructor: mock.courseInstructors[c.courseid] || 'Bilinmiyor',
        color: mock.courseColors[c.courseid] || 'var(--primary)',
      })),
      recentGrades: mock.dash_04_module_status
        .filter(m => m.is_completed && (m.module_type === 'quiz' || m.module_type === 'assign'))
        .slice(0, 5),
    };
    
    const res = await fetchWithRetry(`/api/student/me/home`, fallbackData);
    if (!res.fallback) {
      const raw = res.data as any;
      const mapped = {
        user: {
          id: raw.user_id,
          name: raw.user_name || 'Öğrenci',
          firstName: (raw.user_name || 'Öğrenci').split(' ')[0] || 'Öğrenci',
          email: '',
          program: 'Bilgisayar Mühendisliği · 3. Sınıf',
          photo: 'https://cdn3.pixelcut.app/7/20/uncrop_hero_bdf08a8ca6.jpg',
        },
        courses: (raw.active_courses || []).map((c: any) => {
          const cid = c.course_id;
          return {
            userid: raw.user_id,
            courseid: cid,
            course_fullname: c.course_name,
            course_shortname: c.course_name.split(' ')[0] || `CRS${cid}`,
            course_visible: 1,
            enrollment_status: 0,
            total_visible_modules: c.total_visible_modules ?? 0,
            completed_modules: c.completed_modules ?? 0,
            completion_pct: c.completion_pct ?? 0,
            avg_grade: c.current_grade !== null ? c.current_grade : 0.0,
            next_expected_date: null,
            last_activity_date: '',
            computed_at: '',
            instructor: mock.courseInstructors[cid] || 'Bilinmiyor',
            color: mock.courseColors[cid] || 'var(--primary)',
          };
        }),
        recentGrades: (raw.recent_grades || []).map((rg: any, index: number) => {
          return {
            userid: raw.user_id,
            courseid: 0,
            cmid: index,
            module_type: 'quiz',
            display_name: rg.item_name,
            section_order: 1,
            is_visible: true,
            is_available: true,
            completion_required: 2,
            is_completed: true,
            completion_action: 'submit',
            completion_time: null,
            first_view_time: null,
            view_to_complete_hours: null,
            expected_date: null,
            added_date: null
          };
        }),
      };
      return { data: mapped, fallback: false };
    }
    return res;
  },

  // 2. GET /api/student/me/dashboard (risk premodel analysis outputs)
  getStudentDashboard: async (_uid: string) => {
    const fallbackData = {
      risk_premodel_analysis: {
        risk_score: 24.5,
        risk_level: 'Düşük',
        pass_probability: 0.88,
        will_pass: true,
      },
      basic_values: {
        gpa: mock.dash_02_user_stats.avg_grade,
        streak: mock.dash_02_user_stats.study_streak_days,
        late_assignments: mock.dash_02_user_stats.late_assignment_count,
        focus_score: mock.dash_02_user_stats.focus_score,
      },
    };
    return fetchWithRetry(`/api/student/me/dashboard`, fallbackData);
  },

  // 3. GET /api/student/me/grades
  getStudentGrades: async (_uid: string) => {
    const fallbackData = {
      courses: mock.dash_03_course_progress,
      gradeItems: mock.dash_04_module_status
        .filter(m => m.is_completed && (m.module_type === 'quiz' || m.module_type === 'assign'))
        .map(m => ({
          course: mock.dash_03_course_progress.find(c => c.courseid === m.courseid)?.course_fullname || 'Kurs',
          code: mock.dash_03_course_progress.find(c => c.courseid === m.courseid)?.course_shortname || 'CODE',
          item: m.display_name,
          type: m.module_type,
          weight: m.display_name.includes('Vize') ? 30 : 10,
          grade: m.display_name.includes('Vize') ? 85 : 90,
          max: 100,
          date: m.completion_time ? new Date(m.completion_time * 1000).toISOString().split('T')[0] : '—',
        })),
      gradeTrend: mock.gradeTrend,
    };

    const res = await fetchWithRetry(`/api/student/me/grades`, fallbackData);
    if (!res.fallback) {
      const raw = res.data as any;
      const ongoing = (raw.ongoing_courses || []).map((c: any) => ({
        userid: raw.user_id,
        courseid: c.course_id,
        course_fullname: c.course_name,
        course_shortname: c.course_name.split(' ')[0] || `CRS${c.course_id}`,
        course_visible: 1,
        enrollment_status: 0,
        total_visible_modules: c.total_visible_modules || 20,
        completed_modules: c.completed_modules || 10,
        completion_pct: c.completion_pct || 50,
        avg_grade: c.current_grade !== null ? c.current_grade : 0,
        next_expected_date: c.next_expected_date,
        last_activity_date: '',
        computed_at: '',
      }));

      const completed = (raw.completed_courses || []).map((c: any) => ({
        userid: raw.user_id,
        courseid: c.course_id,
        course_fullname: c.course_name,
        course_shortname: c.course_name.split(' ')[0] || `CRS${c.course_id}`,
        course_visible: 1,
        enrollment_status: 1,
        total_visible_modules: 20,
        completed_modules: 20,
        completion_pct: 100.0,
        avg_grade: c.final_grade !== null ? c.final_grade : 0,
        next_expected_date: null,
        last_activity_date: '',
        computed_at: '',
      }));

      const courses = [...ongoing, ...completed];

      const gradeItems: any[] = [];
      courses.forEach(c => {
        if (c.avg_grade > 0) {
          gradeItems.push({
            course: c.course_fullname,
            code: c.course_shortname,
            item: 'Dönem Sonu Notu',
            type: 'exam',
            weight: 100,
            grade: Math.round(c.avg_grade),
            max: 100,
            date: '2026-06-15',
          });
        }
      });

      const mapped = {
        courses,
        gradeItems: gradeItems.length > 0 ? gradeItems : fallbackData.gradeItems,
        gradeTrend: fallbackData.gradeTrend,
      };
      return { data: mapped, fallback: false };
    }
    return res;
  },

  // 4. GET /api/student/me/learning-path
  getStudentLearningPath: async (_uid: string) => {
    const fallbackData = {
      timeline: [
        { date: '2026-06-17', action: 'Submit', title: 'Calculus I - Ödev 2' },
        { date: '2026-06-16', action: 'View', title: 'Fizik 101 - Lab Raporu Detayları' },
        { date: '2026-06-15', action: 'Submit', title: 'Veri Yapıları - Proje 1' },
      ],
      dataset: mock.dash_01_daily_sessions,
    };

    const res = await fetchWithRetry(`/api/student/me/learning-path`, fallbackData);
    if (!res.fallback) {
      const raw = res.data as any;
      const labels = raw.chartjs_labels || [];
      const durationDataset = (raw.chartjs_datasets || []).find((d: any) => d.label === 'Süre');
      const sessionsDataset = (raw.chartjs_datasets || []).find((d: any) => d.label === 'Oturum');
      const pageviewsDataset = (raw.chartjs_datasets || []).find((d: any) => d.label === 'Sayfa Görüntüleme');

      const dataset = labels.map((label: string, index: number) => {
        const dayMatch = label.match(/\d+/);
        const dayStr = dayMatch ? dayMatch[0].padStart(2, '0') : '01';
        return {
          userid: raw.user_id,
          activity_date: `2026-06-${dayStr}`,
          day_of_week: 0,
          session_count: sessionsDataset ? sessionsDataset.data[index] : 0,
          total_minutes: durationDataset ? durationDataset.data[index] : 0,
          page_views: pageviewsDataset ? pageviewsDataset.data[index] : 0,
        };
      });

      const mapped = {
        timeline: (raw.timeline || []).map((t: any) => ({
          date: t.date_str,
          action: t.is_completed ? 'Submit' : 'View',
          title: `${t.course_name} - ${t.details}`,
        })),
        dataset,
      };
      return { data: mapped, fallback: false };
    }
    return res;
  },

  // 5. GET /api/student/me/competencies
  getStudentCompetencies: async (_uid: string) => {
    const fallbackData = {
      competencies: mock.competencies,
      activityBreakdown: mock.activityBreakdown,
      completionByCourse: mock.dash_03_course_progress.map(c => ({
        course: c.course_fullname,
        completed: c.completed_modules,
        total: c.total_visible_modules,
      })),
    };

    const res = await fetchWithRetry(`/api/student/me/competencies`, fallbackData);
    if (!res.fallback) {
      const raw = res.data as any;

      const competencies = (raw.competencies || []).map((item: any) => {
        const labelMap: Record<string, string> = {
          'OKUMA': 'Okuma ve Anlama',
          'FORUM': 'Forum Katılımı',
          'İZLEME': 'Video İzleme',
          'ÖDEV': 'Sınav ve Ödevler'
        };
        return {
          name: labelMap[item.type] || item.type,
          value: Math.round(item.percentage),
          framework: 'Akademik Yetkinlikler'
        };
      });

      const colors: Record<string, string> = {
        'OKUMA': 'var(--cat-blue)',
        'FORUM': 'var(--cat-sky)',
        'İZLEME': 'var(--brand-sky)',
        'ÖDEV': 'var(--brand-navy)'
      };
      const moodles: Record<string, string> = {
        'OKUMA': 'resource/page',
        'FORUM': 'forum',
        'İZLEME': 'scorm/lesson',
        'ÖDEV': 'assign/quiz'
      };
      const activityBreakdown = (raw.competencies || []).map((item: any) => {
        const labelMap: Record<string, string> = {
          'OKUMA': 'Okuma',
          'FORUM': 'Forum',
          'İZLEME': 'İzleme',
          'ÖDEV': 'Sınav/Ödev'
        };
        return {
          label: labelMap[item.type] || item.type,
          moodle: moodles[item.type] || 'other',
          value: item.completed,
          color: colors[item.type] || 'var(--primary)'
        };
      });

      const completionByCourse = (raw.completion_by_course || []).map((c: any) => ({
        course: c.course,
        completed: c.completed,
        total: c.total
      }));

      const mapped = {
        competencies,
        activityBreakdown,
        completionByCourse: completionByCourse.length > 0 ? completionByCourse : fallbackData.completionByCourse,
      };
      return { data: mapped, fallback: false };
    }
    return res;
  },

  // 6. GET /api/student/me/events
  getStudentEvents: async (_uid: string) => {
    const res = await fetchWithRetry(`/api/student/me/events`, mock.dash_07_upcoming_events);
    if (!res.fallback && res.data && Array.isArray((res.data as any).items)) {
      return { data: (res.data as any).items, fallback: false };
    }
    return res;
  },

  // 7. GET /api/student/me/basic
  getStudentBasic: async (_uid: string) => {
    return fetchWithRetry(`/api/student/me/basic`, mock.dash_02_user_stats);
  },

  // 8. GET /api/student/me/heatmap
  getStudentHeatmap: async (_uid: string) => {
    const res = await fetchWithRetry(`/api/student/me/heatmap`, mock.dash_06_activity_heatmap);
    if (!res.fallback && res.data && Array.isArray((res.data as any).data)) {
      return { data: (res.data as any).data, fallback: false };
    }
    return res;
  },

  // 9. GET /api/student/me/course-analytics
  getStudentCourseAnalytics: async (_uid: string) => {
    const res = await fetchWithRetry(`/api/student/me/course-analytics`, mock.dash_05_course_analytics);
    if (!res.fallback && res.data && Array.isArray((res.data as any).courses)) {
      return { data: (res.data as any).courses, fallback: false };
    }
    return res;
  },
};


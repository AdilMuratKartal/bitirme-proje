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
    // Falls back to mock course progress and student profile combination
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
    return fetchWithRetry(`/api/student/me/home`, fallbackData);
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
    return fetchWithRetry(`/api/student/me/grades`, fallbackData);
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
    return fetchWithRetry(`/api/student/me/learning-path`, fallbackData);
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
    return fetchWithRetry(`/api/student/me/competencies`, fallbackData);
  },

  // 6. GET /api/student/me/events
  getStudentEvents: async (_uid: string) => {
    const res = await fetchWithRetry(`/api/student/me/events`, mock.dash_07_upcoming_events);
    // Backend { items: [...] } döndürüyor, düz diziye aç
    if (!res.fallback && res.data && Array.isArray((res.data as any).items)) {
      return { data: (res.data as any).items, fallback: false };
    }
    return res; // fallback zaten düz dizi
  },

  // 7. GET /api/student/me/basic
  getStudentBasic: async (_uid: string) => {
    return fetchWithRetry(`/api/student/me/basic`, mock.dash_02_user_stats);
  },

  // 8. GET /api/student/me/heatmap
  getStudentHeatmap: async (_uid: string) => {
    return fetchWithRetry(`/api/student/me/heatmap`, mock.dash_06_activity_heatmap);
  },

  // 9. GET /api/student/me/course-analytics
  getStudentCourseAnalytics: async (_uid: string) => {
    return fetchWithRetry(`/api/student/me/course-analytics`, mock.dash_05_course_analytics);
  },
};


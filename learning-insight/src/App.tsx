import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebaseConfig';
import { apiService } from './services/apiService';
import { Header, Sidebar, Skeleton, Toast } from './components';
import { LoginScreen } from './screens/LoginScreen';
import { HomeScreen } from './screens/HomeScreen';
import { CoursesScreen } from './screens/CoursesScreen';
import { CourseDetailScreen } from './screens/CourseDetailScreen';
import { GradesScreen } from './screens/GradesScreen';
import { CalendarScreen } from './screens/CalendarScreen';
import { CompetenciesScreen } from './screens/CompetenciesScreen';
import { LearningPathScreen } from './screens/LearningPathScreen';
import { ActivityHeatmapScreen } from './screens/ActivityHeatmapScreen';
import { DatabaseViewerScreen } from './screens/DatabaseViewerScreen';
import { PlaceholderScreen } from './screens/PlaceholderScreen';

const getInitTime = () => {
  if (typeof window !== 'undefined') {
    const t0 = (window as any).__liT0 || performance.now();
    (window as any).__liT0 = t0;
    return t0;
  }
  return 0;
};

const App: React.FC = () => {
  const [authed, setAuthed] = useState(false);
  const [page, setPage] = useState<string>('home');
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showFallbackToast, setShowFallbackToast] = useState(false);
  
  // Performance indicators
  const [perf, setPerf] = useState<{ open: number | null; nav: number | null }>({ open: null, nav: null });
  const navStart = useRef<number | null>(null);

  // API response state
  const [apiData, setApiData] = useState<any>(null);

  // Initial load time tracking
  useEffect(() => {
    const t0 = getInitTime();
    setPerf((p) => ({ ...p, open: Math.round(performance.now() - t0) }));
  }, []);

  // Screen navigation duration tracking
  useLayoutEffect(() => {
    if (navStart.current !== null) {
      const ms = performance.now() - navStart.current;
      navStart.current = null;
      setPerf((p) => ({ ...p, nav: Math.round(ms * 10) / 10 }));
    }
  });

  // Concurrent API data loading with try-retry fallback mapping
  const loadAllData = async (userUid: string) => {
    setLoading(true);
    setShowFallbackToast(false);

    try {
      const [
        homeRes,
        dashboardRes,
        gradesRes,
        learningPathRes,
        competenciesRes,
        eventsRes,
        basicRes,
        heatmapRes,
        courseAnalyticsRes
      ] = await Promise.all([
        apiService.getStudentHome(userUid),
        apiService.getStudentDashboard(userUid),
        apiService.getStudentGrades(userUid),
        apiService.getStudentLearningPath(userUid),
        apiService.getStudentCompetencies(userUid),
        apiService.getStudentEvents(userUid),
        apiService.getStudentBasic(userUid),
        apiService.getStudentHeatmap(userUid),
        apiService.getStudentCourseAnalytics(userUid)
      ]);

      const isAnyFallback =
        homeRes.fallback ||
        dashboardRes.fallback ||
        gradesRes.fallback ||
        learningPathRes.fallback ||
        competenciesRes.fallback ||
        eventsRes.fallback ||
        basicRes.fallback ||
        heatmapRes.fallback ||
        courseAnalyticsRes.fallback;

      setApiData({
        home: homeRes.data,
        dashboard: dashboardRes.data,
        grades: gradesRes.data,
        learningPath: learningPathRes.data,
        competencies: competenciesRes.data,
        events: eventsRes.data,
        basic: basicRes.data,
        heatmap: heatmapRes.data,
        courseAnalytics: courseAnalyticsRes.data
      });

      if (isAnyFallback) {
        setShowFallbackToast(true);
      }
    } catch (error) {
      console.error("Critical API data fetch error:", error);
      setShowFallbackToast(true);
    } finally {
      setLoading(false);
    }
  };

  // Listen to Firebase Auth state
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        setAuthed(true);
        loadAllData(user.uid);
      } else {
        setAuthed(false);
        setApiData(null);
      }
    });
    return () => unsubscribe();
  }, []);

  const navigate = (key: string) => {
    navStart.current = performance.now();
    if (key === 'logout') {
      auth.signOut();
      return;
    }
    setPage(key);
  };

  const hud = (
    <div className="li-perf" title="Açılış: ilk render süresi · Gezinme: ekran geçiş süresi">
      <span className="material-icons">bolt</span>
      <span>
        Açılış <b className="li-num">{perf.open !== null ? `${perf.open}ms` : '—'}</b>
      </span>
      <span className="li-perf__sep">·</span>
      <span>
        Gezinme <b className="li-num">{perf.nav !== null ? `${perf.nav}ms` : '—'}</b>
      </span>
    </div>
  );

  // Not authenticated view
  if (!authed) {
    return (
      <>
        <LoginScreen onLogin={() => {}} />
        {hud}
      </>
    );
  }

  // Authenticated state screens router
  let screen: React.ReactNode;
  
  if (loading || !apiData) {
    // Render the skeleton loader screen when fetching API data
    screen = <Skeleton />;
  } else {
    switch (page) {
      case 'home':
        screen = <HomeScreen onNavigate={navigate} apiData={apiData} />;
        break;
      case 'courses':
        screen = (
          <CoursesScreen
            onNavigate={navigate}
            onSelectCourse={(id) => setSelectedCourseId(id)}
            apiData={apiData}
          />
        );
        break;
      case 'coursedetail':
        screen = (
          <CourseDetailScreen
            courseId={selectedCourseId || 201}
            onBack={() => navigate('courses')}
            apiData={apiData}
          />
        );
        break;
      case 'grades':
        screen = <GradesScreen apiData={apiData} />;
        break;
      case 'calendar':
        screen = <CalendarScreen apiData={apiData} />;
        break;
      case 'heatmap':
        screen = <ActivityHeatmapScreen apiData={apiData} />;
        break;
      case 'competencies':
        screen = <CompetenciesScreen apiData={apiData} />;
        break;
      case 'lineage':
        screen = <DatabaseViewerScreen apiData={apiData} />;
        break;
      case 'learning':
        screen = <LearningPathScreen apiData={apiData} />;
        break;
      case 'certificates':
      case 'account':
        screen = <PlaceholderScreen page={page} onNavigate={navigate} />;
        break;
      default:
        screen = <PlaceholderScreen page={page} onNavigate={navigate} />;
    }
  }

  return (
    <div className="li-app">
      <Header onToggleSidebar={() => setCollapsed((c) => !c)} onNavigate={navigate} />
      <div className="li-app__body">
        <Sidebar
          page={page}
          onNavigate={navigate}
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
        />
        <main className="li-app__content">{screen}</main>
      </div>
      
      {hud}

      <Toast
        show={showFallbackToast}
        message="Gerçek zamanlı sunucuya bağlanılamadı. Önbellekteki veriler gösteriliyor."
        onClose={() => setShowFallbackToast(false)}
      />
    </div>
  );
};

export default App;
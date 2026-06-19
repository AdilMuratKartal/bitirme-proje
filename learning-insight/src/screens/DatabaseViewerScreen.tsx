import React, { useState } from 'react';
import { Card } from '../components';
import {
  dash_04_module_status,
} from '../data/mockData';

interface DatabaseViewerScreenProps {
  apiData: {
    learningPath: {
      dataset: any[];
    };
    basic: any;
    grades: {
      courses: any[];
    };
    courseAnalytics: any[];
    heatmap: any[];
    events: any[];
  };
}

interface TableMeta {
  id: string;
  name: string;
  pk: string;
  source: string;
  dependency: string;
  rows: any[];
  headers: string[];
}

export const DatabaseViewerScreen: React.FC<DatabaseViewerScreenProps> = ({ apiData }) => {
  const [activeTab, setActiveTab] = useState<string>('dash_01');

  const tables: TableMeta[] = [
    {
      id: 'dash_01',
      name: 'dash_01_daily_sessions.csv',
      pk: '(userid, activity_date)',
      source: 'mdl_log (aylık CSV\'ler)',
      dependency: 'Sadece log\'a bağlı',
      rows: apiData.learningPath?.dataset || [],
      headers: ['userid', 'activity_date', 'day_of_week', 'session_count', 'total_minutes', 'page_views'],
    },
    {
      id: 'dash_02',
      name: 'dash_02_user_stats.csv',
      pk: 'userid',
      source: 'dash_01 + dash_04 + mdl_grade_grades + mdl_grade_items',
      dependency: 'dash_01 ve dash_04\'e bağımlı',
      rows: apiData.basic ? [apiData.basic] : [],
      headers: [
        'userid',
        'focus_score',
        'focus_score_delta_pct',
        'avg_grade',
        'avg_grade_delta',
        'study_streak_days',
        'streak_delta',
        'late_assignment_count',
        'late_assignment_delta',
        'total_courses_active',
        'total_study_minutes',
        'avg_session_minutes',
        'sessions_per_active_day',
        'last_active_date',
        'computed_at',
      ],
    },
    {
      id: 'dash_03',
      name: 'dash_03_course_progress.csv',
      pk: '(userid, courseid)',
      source: 'dash_04 + mdl_log + mdl_course + mdl_enrol + mdl_grade',
      dependency: 'dash_04 ve log\'a bağımlı',
      rows: apiData.grades?.courses || [],
      headers: [
        'userid',
        'courseid',
        'course_fullname',
        'course_shortname',
        'course_visible',
        'enrollment_status',
        'total_visible_modules',
        'completed_modules',
        'completion_pct',
        'avg_grade',
        'next_expected_date',
        'last_activity_date',
        'computed_at',
      ],
    },
    {
      id: 'dash_04',
      name: 'dash_04_module_status.csv',
      pk: '(userid, cmid)',
      source: 'mdl_course_modules + mdl_modules + mdl_grade_items + mdl_log',
      dependency: 'Moodle ham tablolarına bağlı (En ağır, ilk çalışır)',
      rows: dash_04_module_status,
      headers: [
        'userid',
        'courseid',
        'cmid',
        'module_type',
        'display_name',
        'section_order',
        'is_visible',
        'is_available',
        'completion_required',
        'is_completed',
        'completion_action',
        'completion_time',
        'first_view_time',
        'view_to_complete_hours',
        'expected_date',
        'added_date',
      ],
    },
    {
      id: 'dash_05',
      name: 'dash_05_course_analytics.csv',
      pk: '(userid, courseid)',
      source: 'dash_04 + mdl_log',
      dependency: 'dash_04 ve log\'a bağımlı',
      rows: apiData.courseAnalytics || [],
      headers: [
        'userid',
        'courseid',
        'most_common_module_type',
        'assign_total',
        'assign_completed',
        'assign_completion_rate',
        'quiz_total',
        'quiz_completed',
        'quiz_completion_rate',
        'resource_total',
        'resource_viewed',
        'resource_view_rate',
        'forum_total',
        'forum_interactions',
        'forum_interaction_rate',
        'page_total',
        'page_viewed',
        'page_view_rate',
        'avg_daily_minutes',
        'total_active_days',
        'total_events',
        'last_activity_date',
      ],
    },
    {
      id: 'dash_06',
      name: 'dash_06_activity_heatmap.csv',
      pk: '(userid, weekday, hour)',
      source: 'mdl_log',
      dependency: 'Sadece log\'a bağlı',
      rows: (apiData.heatmap || []).slice(0, 48), // Limit heatmap rows in database viewer to avoid crash
      headers: ['userid', 'weekday', 'hour', 'event_count', 'session_starts'],
    },
    {
      id: 'dash_07',
      name: 'dash_07_upcoming_events.csv',
      pk: '(userid, cmid)',
      source: 'dash_04 + mdl_course',
      dependency: 'Sadece dash_04\'e bağımlı',
      rows: apiData.events || [],
      headers: [
        'userid',
        'courseid',
        'cmid',
        'module_type',
        'display_name',
        'course_name',
        'course_short',
        'event_date',
        'timestart',
        'days_until',
        'is_overdue',
        'is_completed',
      ],
    },
  ];

  const currentTable = tables.find((t) => t.id === activeTab) || tables[0];

  const renderVal = (v: any) => {
    if (v === null || v === undefined) return 'NULL';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    return String(v);
  };

  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>Veri İletim Hattı (Data Lineage)</h1>
        <p>Moodle LMS veri tabanından türetilen ve önyüze beslenen 7 dashboard tablosunun detayları</p>
      </div>

      {/* Tabs */}
      <div className="li-filters" style={{ marginBottom: '20px' }}>
        {tables.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-pill)',
              border: activeTab === t.id ? 'none' : '1px solid var(--border-default)',
              backgroundColor: activeTab === t.id ? 'var(--primary)' : 'var(--surface-card)',
              color: activeTab === t.id ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: '600',
              fontSize: '13px',
              transition: 'background var(--dur-fast)',
            }}
          >
            {t.id}
          </button>
        ))}
      </div>

      {/* Lineage Info Card */}
      <Card title={currentTable.name} style={{ marginBottom: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '8px' }}>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text-disabled)', textTransform: 'uppercase', fontWeight: 'bold' }}>
              Primary Key (PK)
            </div>
            <div className="li-num" style={{ fontSize: '15px', fontWeight: 'bold', marginTop: '4px', color: 'var(--primary)' }}>
              {currentTable.pk}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text-disabled)', textTransform: 'uppercase', fontWeight: 'bold' }}>
              Kaynak Tablolar
            </div>
            <div style={{ fontSize: '14px', fontWeight: 'bold', marginTop: '4px', color: 'var(--text-primary)' }}>
              {currentTable.source}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text-disabled)', textTransform: 'uppercase', fontWeight: 'bold' }}>
              Bağımlılık Zinciri
            </div>
            <div style={{ fontSize: '14px', fontWeight: 'bold', marginTop: '4px', color: 'var(--text-primary)' }}>
              {currentTable.dependency}
            </div>
          </div>
        </div>
      </Card>

      {/* Data Viewer Card */}
      <Card title="Tablo Kayıtları">
        <p className="li-card__sub" style={{ margin: '-8px 0 16px 0' }}>
          Önyüzde saklanan ve simüle edilen gerçek veri kayıtları ({currentTable.id === 'dash_06' ? 'ilk 48 satır gösterilmektedir' : `${currentTable.rows.length} satır`})
        </p>

        <div className="li-tablewrap">
          <table className="li-table">
            <thead>
              <tr>
                {currentTable.headers.map((h) => (
                  <th key={h} style={{ fontSize: '11px', padding: '8px' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {currentTable.rows.map((row, idx) => (
                <tr key={idx}>
                  {currentTable.headers.map((h) => (
                    <td
                      key={h}
                      className="li-num"
                      style={{
                        padding: '10px 8px',
                        fontSize: '13px',
                        color: typeof row[h] === 'number' ? 'var(--text-primary)' : 'var(--text-secondary)',
                      }}
                    >
                      {renderVal(row[h])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};


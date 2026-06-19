import React from 'react';
import { Button, Card, Tag, StatCard } from '../components';
import {
  dash_04_module_status,
  courseColors,
  courseInstructors,
} from '../data/mockData';

interface CourseDetailScreenProps {
  courseId: number;
  onBack: () => void;
  apiData: any;
}

const MODULE_TYPE_META: Record<string, { label: string; tone: string }> = {
  assign: { label: 'Ödev', tone: 'orange' },
  quiz: { label: 'Quiz', tone: 'purple' },
  resource: { label: 'Kaynak', tone: 'blue' },
  forum: { label: 'Forum', tone: 'sky' },
  page: { label: 'Sayfa', tone: 'green' },
};

export const CourseDetailScreen: React.FC<CourseDetailScreenProps> = ({ courseId, onBack, apiData }) => {
  const courses = apiData.home.courses || [];
  const course = courses.find((c: any) => c.courseid === courseId);
  
  const instructor = courseInstructors[courseId] || 'Dr. Bilinmiyor';
  const color = courseColors[courseId] || 'var(--primary)';

  // Fallback to local detailed module status if not provided by endpoints
  const modules = dash_04_module_status.filter((m) => m.courseid === courseId);

  // Get analytics for this course from apiData.courseAnalytics
  const analyticsList = apiData.courseAnalytics || [];
  const analytics = analyticsList.find((a: any) => a.courseid === courseId);

  if (!course) {
    return (
      <div className="li-page">
        <h1>Kurs Bulunamadı</h1>
        <Button onClick={onBack}>Geri Dön</Button>
      </div>
    );
  }

  return (
    <div className="li-page">
      <div className="li-page__head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="li-num" style={{ fontSize: '14px', fontWeight: 'bold', color }}>
              {course.course_shortname}
            </span>
            <Tag tone={course.enrollment_status === 0 ? 'green' : 'danger'}>
              {course.enrollment_status === 0 ? 'Aktif Kayıt' : 'Süresi Doldu'}
            </Tag>
          </div>
          <h1 style={{ marginTop: '4px' }}>{course.course_fullname}</h1>
          <p>Eğitmen: {instructor}</p>
        </div>
        <Button variant="secondary" startIcon={<span className="material-icons">arrow_back</span>} onClick={onBack}>
          Kurslara Dön
        </Button>
      </div>

      {/* Course Analytics summary from apiData.courseAnalytics */}
      {analytics && (
        <div style={{ marginBottom: '24px' }}>
          <h2>Kurs Analitiği</h2>
          <p className="li-card__sub" style={{ marginBottom: '16px' }}>
            Bu derse ait etkileşim oranları ve çalışma süreleri <span className="li-src">GET /api/student/me/course-analytics</span>
          </p>
          <div className="li-home__kpis" style={{ marginBottom: '20px' }}>
            <StatCard
              label="Ödev İlerlemesi"
              value={`${analytics.assign_completed}/${analytics.assign_total}`}
              tone="gold"
              delta={`${Math.round(analytics.assign_completion_rate)}%`}
              deltaDir={analytics.assign_completion_rate >= 80 ? 'up' : 'flat'}
              caption="tamamlanma oranı"
              icon={<span className="material-icons">assignment</span>}
            />
            <StatCard
              label="Quiz İlerlemesi"
              value={`${analytics.quiz_completed}/${analytics.quiz_total}`}
              tone="purple"
              delta={`${Math.round(analytics.quiz_completion_rate)}%`}
              deltaDir={analytics.quiz_completion_rate >= 80 ? 'up' : 'flat'}
              caption="tamamlanma oranı"
              icon={<span className="material-icons">fact_check</span>}
            />
            <StatCard
              label="Kaynak Okuma"
              value={`${analytics.resource_viewed}/${analytics.resource_total}`}
              tone="primary"
              delta={`${Math.round(analytics.resource_view_rate)}%`}
              deltaDir={analytics.resource_view_rate >= 80 ? 'up' : 'flat'}
              caption="görüntüleme oranı"
              icon={<span className="material-icons">menu_book</span>}
            />
            <StatCard
              label="Günlük Ort. Süre"
              value={`${analytics.avg_daily_minutes} dk`}
              tone="green"
              delta={`${analytics.total_active_days} gün`}
              deltaDir="up"
              caption="toplam aktif gün"
              icon={<span className="material-icons">query_builder</span>}
            />
          </div>
        </div>
      )}

      {/* Module Status list */}
      <Card title="Ders Modülleri & Tamamlanma Durumları">
        <p className="li-card__sub">
          Moodle etkinlik listesi ve durumları <span className="li-src">dash_04_module_status.csv</span>
        </p>
        <div className="li-tablewrap">
          <table className="li-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }} className="ta-c">
                  Durum
                </th>
                <th>Etkinlik Adı</th>
                <th>Tür</th>
                <th className="ta-c">Bölüm Sırası</th>
                <th className="ta-r">Harcanan Süre</th>
                <th>Deadline</th>
                <th>Tamamlanma Eylemi</th>
              </tr>
            </thead>
            <tbody>
              {modules.length === 0 ? (
                <tr>
                  <td colSpan={7} className="ta-c li-table__muted">
                    Bu derse kayıtlı modül bulunamadı.
                  </td>
                </tr>
              ) : (
                modules.map((m, i) => {
                  const meta = MODULE_TYPE_META[m.module_type] || { label: m.module_type, tone: 'gray' };
                  const durationText = m.view_to_complete_hours
                    ? `${m.view_to_complete_hours.toFixed(1)} saat`
                    : '—';
                  
                  return (
                    <tr key={i}>
                      <td className="ta-c">
                        {m.is_completed ? (
                          <span className="material-icons" style={{ color: 'var(--success)' }}>
                            check_circle
                          </span>
                        ) : (
                          <span className="material-icons" style={{ color: 'var(--neutral-400)' }}>
                            radio_button_unchecked
                          </span>
                        )}
                      </td>
                      <td className="li-table__name">{m.display_name}</td>
                      <td>
                        <Tag tone={meta.tone} variant="soft" size="sm">
                          {meta.label}
                        </Tag>
                      </td>
                      <td className="ta-c li-num">{m.section_order}</td>
                      <td className="ta-r li-num">{durationText}</td>
                      <td className="li-num li-table__muted">{m.expected_date || '—'}</td>
                      <td>
                        {m.is_completed ? (
                          <span style={{ fontSize: '13px' }}>
                            <span className="li-num" style={{ fontWeight: 'semibold' }}>
                              {m.completion_action === 'submit' ? 'Teslim edildi' : 'Görüntülendi'}
                            </span>
                            {m.completion_time && (
                              <div style={{ fontSize: '11px', color: 'var(--text-disabled)' }}>
                                {new Date(m.completion_time * 1000).toLocaleDateString('tr-TR')}
                              </div>
                            )}
                          </span>
                        ) : (
                          <span className="li-table__muted" style={{ fontSize: '13px' }}>
                            Kalan
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

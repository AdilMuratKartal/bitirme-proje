import React from 'react';
import { Button, Card, Tag, StatCard } from '../components';
import { courseColors } from '../data/mockData';

interface CourseDetailScreenProps {
  courseId: number;
  onBack: () => void;
  apiData: any;
}

const pct = (v: any) => (v != null ? `${Math.round(v)}%` : '—');

export const CourseDetailScreen: React.FC<CourseDetailScreenProps> = ({ courseId, onBack, apiData }) => {
  const courses = apiData.home.courses || [];
  const course = courses.find((c: any) => c.courseid === courseId);
  const color = courseColors[courseId] || 'var(--primary)';

  // Gerçek kurs analitiği (dash_course_analytics)
  const analytics = (apiData.courseAnalytics || []).find((a: any) => a.courseid === courseId);

  // Bu kursun gerçek not kalemleri (dash_grade_items, courseid ile filtre)
  const items = (apiData.grades?.gradeItems || []).filter((g: any) => g.courseid === courseId);

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
        </div>
        <Button variant="secondary" startIcon={<span className="material-icons">arrow_back</span>} onClick={onBack}>
          Kurslara Dön
        </Button>
      </div>

      {/* Kurs ilerleme özeti (dash_course_progress) */}
      <div className="li-home__kpis" style={{ marginBottom: 20 }}>
        <StatCard label="Tamamlanma" value={pct(course.completion_pct)} tone="primary"
          caption="görünür modüller" icon={<span className="material-icons">donut_large</span>} />
        <StatCard label="Modüller" value={`${course.completed_modules ?? 0}/${course.total_visible_modules ?? 0}`}
          tone="gold" caption="tamamlanan / toplam" icon={<span className="material-icons">checklist</span>} />
        <StatCard label="Ortalama Not" value={course.avg_grade ? Math.round(course.avg_grade).toString() : '—'}
          tone="green" caption="kurs not ortalaması" icon={<span className="material-icons">grade</span>} />
        <StatCard label="Sıradaki" value={course.next_expected_date || '—'}
          tone="purple" caption="yaklaşan teslim" icon={<span className="material-icons">event</span>} />
      </div>

      {/* Gerçek kurs analitiği (dash_course_analytics) */}
      {analytics && (
        <Card title="Kurs Analitiği" style={{ marginBottom: 20 }}>
          <p className="li-card__sub">
            Etkileşim oranları ve çalışma süresi <span className="li-src">GET /api/student/me/course-analytics</span>
          </p>
          <div className="li-home__kpis">
            <StatCard label="Ödev Tamamlama" value={pct(analytics.assign_completion_rate)} tone="gold"
              icon={<span className="material-icons">assignment</span>} />
            <StatCard label="Quiz Tamamlama" value={pct(analytics.quiz_completion_rate)} tone="purple"
              icon={<span className="material-icons">fact_check</span>} />
            <StatCard label="Sayfa Görüntüleme" value={pct(analytics.page_view_rate)} tone="primary"
              caption={`${analytics.page_viewed ?? 0}/${analytics.page_total ?? 0} sayfa`}
              icon={<span className="material-icons">menu_book</span>} />
            <StatCard label="Forum Etkileşim" value={pct(analytics.forum_interaction_rate)} tone="sky"
              caption={`${analytics.forum_interactions ?? 0}/${analytics.forum_total ?? 0} konu`}
              icon={<span className="material-icons">forum</span>} />
            <StatCard label="Günlük Ort. Süre" value={`${Math.round(analytics.avg_daily_minutes ?? 0)} dk`}
              tone="green" icon={<span className="material-icons">query_builder</span>} />
          </div>
        </Card>
      )}

      {/* Bu kursun gerçek not kalemleri (dash_grade_items) */}
      <Card title="Bu Dersin Notları">
        <p className="li-card__sub">
          Hesaplanabilir ödev/quiz notları + geçti/kaldı <span className="li-src">GET /api/student/me/grades · grade_items</span>
        </p>
        <div className="li-tablewrap">
          <table className="li-table">
            <thead>
              <tr>
                <th>Kalem</th>
                <th>Tür</th>
                <th className="ta-r">Not</th>
                <th className="ta-c">Durum</th>
                <th>Tarih</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="ta-c li-table__muted">
                    Bu ders için hesaplanabilir not kalemi bulunamadı.
                  </td>
                </tr>
              ) : (
                items.map((g: any, i: number) => (
                  <tr key={i}>
                    <td className="li-table__name">{g.item}</td>
                    <td><Tag tone="gray" variant="soft" size="sm">{g.type}</Tag></td>
                    <td className="ta-r li-num li-table__grade">{g.grade}<span className="li-table__max">/{g.max}</span></td>
                    <td className="ta-c">
                      {g.passed === true ? (
                        <Tag tone="green" variant="soft" size="sm">Geçti</Tag>
                      ) : g.passed === false ? (
                        <Tag tone="red" variant="soft" size="sm">Kaldı</Tag>
                      ) : (
                        <span className="li-table__muted">—</span>
                      )}
                    </td>
                    <td className="li-num li-table__muted">{g.date}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

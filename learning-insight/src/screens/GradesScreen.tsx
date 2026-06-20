import React from 'react';
import { Card, Tag, StatCard } from '../components';
import { BarChart, LineChart } from '../components/Charts';
import { courseColors, courseCredits } from '../data/mockData';

interface GradesScreenProps {
  apiData: any;
}

function letterFor(g: number): string {
  if (g >= 90) return 'AA';
  if (g >= 85) return 'BA';
  if (g >= 80) return 'BB';
  if (g >= 70) return 'CB';
  if (g >= 60) return 'CC';
  if (g >= 50) return 'DC';
  if (g > 0) return 'DD';
  return '—';
}

const TYPE_TONE: Record<string, string> = { quiz: 'sky', exam: 'purple', assign: 'orange' };
const TYPE_LABEL: Record<string, string> = { quiz: 'Quiz', exam: 'Sınav', assign: 'Ödev' };

export const GradesScreen: React.FC<GradesScreenProps> = ({ apiData }) => {
  const { courses, gradeItems, gradeTrend, recommendations } = apiData.grades;

  const gradedCourses = (courses || []).filter((c: any) => c.avg_grade > 0);
  const avg = gradedCourses.length > 0
    ? Math.round(gradedCourses.reduce((sum: number, c: any) => sum + c.avg_grade, 0) / gradedCourses.length)
    : 0;
  
  const best = gradedCourses.length > 0
    ? gradedCourses.reduce((prev: any, current: any) => (current.avg_grade > prev.avg_grade ? current : prev))
    : { avg_grade: 0, course_fullname: '—' };

  // Sum active completed course credits
  const totalCredits = (courses || [])
    .filter((c: any) => c.completion_pct === 100)
    .reduce((sum: number, c: any) => sum + (courseCredits[c.courseid] || 0), 0) + 72; // baseline + completed

  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>Notlarım</h1>
        <p>Dönem ortalaması, ders bazlı not dağılımı ve gradebook kalemleri</p>
      </div>

      <div className="li-home__kpis li-home__kpis--3">
        <StatCard
          label="Genel Ortalama"
          value={avg.toString()}
          tone="primary"
          delta="3"
          deltaDir="up"
          caption="GANO: 3.31"
          icon={<span className="material-icons">analytics</span>}
        />
        <StatCard
          label="En Yüksek Not"
          value={best.avg_grade.toString()}
          tone="green"
          caption={best.course_fullname}
          icon={<span className="material-icons">military_tech</span>}
        />
        <StatCard
          label="Tamamlanan Kredi"
          value={totalCredits.toString()}
          tone="gold"
          caption="240 toplam AKTS"
          icon={<span className="material-icons">school</span>}
        />
      </div>
      
      {recommendations && recommendations.length > 0 && (
        <Card title="Akademik Gelişim Önerileri" style={{ marginBottom: '24px', borderLeft: '4px solid var(--primary)' }}>
          <p className="li-card__sub" style={{ margin: '-8px 0 12px 0' }}>
            Not ve katılım istatistiklerinize dayanarak başarı şansınızı artıracak faktörler <span className="li-src">GET /api/student/me/grades</span>
          </p>
          <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '14px', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {recommendations.map((rec: string, idx: number) => (
              <li key={idx}>{rec}</li>
            ))}
          </ul>
        </Card>
      )}

      <div className="li-grades__charts">
        <Card title="Ders Bazlı Not">
          <p className="li-card__sub">
            Kurs toplam notu <span className="li-src">GET /api/student/me/grades</span>
          </p>
          <BarChart
            labels={gradedCourses.map((c: any) => c.course_shortname)}
            data={gradedCourses.map((c: any) => c.avg_grade)}
            colors={gradedCourses.map((c: any) => courseColors[c.courseid] || 'var(--primary)')}
            height={230}
          />
        </Card>
        {gradeTrend.terms.length > 0 && (
          <Card title="Not Eğilimi (Aylık Ortalama)">
            <p className="li-card__sub">
              Aylık ortalama normalize not <span className="li-src">GET /api/student/me/grades · grade_items</span>
            </p>
            <LineChart
              labels={gradeTrend.terms}
              datasets={[{ label: 'Ortalama Not', data: gradeTrend.gpa, color: 'var(--cat-emerald)' }]}
              yMax={100}
              height={230}
            />
          </Card>
        )}
      </div>

      <Card title="Gradebook" className="li-grades__table">
        <p className="li-card__sub">
          Moodle Not Defteri Kalemleri <span className="li-src">GET /api/student/me/grades</span>
        </p>
        <div className="li-tablewrap">
          <table className="li-table">
            <thead>
              <tr>
                <th>Ders</th>
                <th>Kalem</th>
                <th>Tür</th>
                <th className="ta-r">Ağırlık</th>
                <th className="ta-r">Not</th>
                <th className="ta-c">Harf</th>
                <th className="ta-c">Durum</th>
                <th>Dağılım</th>
                <th>Tarih</th>
              </tr>
            </thead>
            <tbody>
              {gradeItems.map((g: any, i: number) => (
                <tr key={i}>
                  <td className="li-table__name">{g.course}</td>
                  <td>{g.item}</td>
                  <td>
                    <Tag tone={TYPE_TONE[g.type] || 'gray'} variant="soft" size="sm">
                      {TYPE_LABEL[g.type] || g.type}
                    </Tag>
                  </td>
                  <td className="ta-r li-num li-table__muted">{g.weight != null ? `%${g.weight}` : '—'}</td>
                  <td className="ta-r li-num li-table__grade">
                    {g.grade}
                    <span className="li-table__max">/{g.max}</span>
                  </td>
                  <td className="ta-c">
                    <Tag
                      tone={g.grade >= 80 ? 'green' : g.grade >= 60 ? 'amber' : 'red'}
                      variant="soft"
                      size="sm"
                    >
                      {letterFor(g.grade)}
                    </Tag>
                  </td>
                  <td className="ta-c">
                    {g.passed === true ? (
                      <Tag tone="green" variant="soft" size="sm">Geçti</Tag>
                    ) : g.passed === false ? (
                      <Tag tone="red" variant="soft" size="sm">Kaldı</Tag>
                    ) : (
                      <span className="li-table__muted">—</span>
                    )}
                  </td>
                  <td>
                    <div className="li-table__bar">
                      <span
                        style={{
                          width: `${g.grade}%`,
                          background:
                            g.grade >= 80
                              ? 'var(--success)'
                              : g.grade >= 60
                              ? 'var(--cat-amber)'
                              : 'var(--danger)',
                        }}
                      ></span>
                    </div>
                  </td>
                  <td className="li-num li-table__muted">{g.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

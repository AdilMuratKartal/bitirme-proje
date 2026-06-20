import React from 'react';
import { Card, StatCard, Avatar, Tag } from '../components';
import { LineChart, BarChart, DoughnutChart } from '../components/Charts';
import { courseColors } from '../data/mockData';

interface HomeScreenProps {
  onNavigate: (page: string) => void;
  apiData: any;
}

// Mini calendar component for dashboard
const MiniCalendar: React.FC<{ events: any[] }> = ({ events }) => {
  const days = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];
  const today = 15; // Simulated date (June 15, 2026)
  
  // Group events by day of month (extracting from YYYY-MM-DD)
  const eventDays = events.reduce((acc, event) => {
    const day = parseInt(event.event_date.split('-')[2], 10);
    if (!isNaN(day)) {
      acc[day] = acc[day] || [];
      acc[day].push(event);
    }
    return acc;
  }, {} as Record<number, any[]>);

  const cells: (number | null)[] = [];
  // Offset of 3 days to match starting day (e.g. Wednesday)
  for (let i = 0; i < 3; i++) cells.push(null);
  for (let d = 1; d <= 30; d++) cells.push(d); // June has 30 days

  const legend = [
    ['Bugün', 'var(--primary)'],
    ['Geçmiş', 'var(--cat-amber)'],
    ['Yaklaşan', 'var(--danger)'],
    ['Gelecek', 'var(--success)'],
  ];

  const dotColor = (d: number) => {
    const evs = eventDays[d];
    if (!evs) return null;
    const ev = evs[0];
    if (d === today) return 'var(--primary)';
    if (ev.is_completed) return 'var(--success)';
    if (ev.is_overdue) return 'var(--danger)';
    if (ev.days_until > 0 && ev.days_until <= 3) return 'var(--danger)';
    return 'var(--cat-amber)';
  };

  return (
    <div className="li-cal">
      <div className="li-cal__legend">
        {legend.map(([label, color]) => (
          <span key={label}>
            <i style={{ background: color }}></i>
            {label}
          </span>
        ))}
      </div>
      <div className="li-cal__month">Haziran 2026</div>
      <div className="li-cal__grid">
        {days.map((d) => (
          <span key={d} className="li-cal__dow">
            {d}
          </span>
        ))}
        {cells.map((d, i) => (
          <span key={i} className={`li-cal__day ${d === today ? 'is-today' : ''}`}>
            {d || ''}
            {d && dotColor(d) ? (
              <i className="li-cal__dot" style={{ background: dotColor(d) || '' }}></i>
            ) : null}
          </span>
        ))}
      </div>
    </div>
  );
};

export const HomeScreen: React.FC<HomeScreenProps> = ({ onNavigate, apiData }) => {
  const { home, dashboard, learningPath, competencies, events } = apiData;
  const user = home.user;
  const courses = home.courses;
  const risk = dashboard.risk_premodel_analysis;
  const basic = dashboard.basic_values;

  // Risk verisi henüz hesaplanmamış olabilir (dash_risk boş → freshness: pending)
  const hasRisk = risk && risk.risk_level != null;
  const riskLevelText = hasRisk ? risk.risk_level : 'Hesaplanıyor';
  const passProbText = risk && risk.pass_probability != null ? `%${Math.round(risk.pass_probability * 100)}` : '—';
  const riskScoreText = risk && risk.risk_score != null ? `%${risk.risk_score}` : '—';

  // Aggregate daily minutes from learningPath dataset for the LineChart
  const weekLabels = (learningPath.dataset || []).map((d: any) => {
    const parts = d.activity_date.split('-');
    return `${parseInt(parts[2], 10)} Haz`;
  });
  const weekMinutes = (learningPath.dataset || []).map((d: any) => d.total_minutes);

  // Active courses list
  const activeCourses = courses.filter((c: any) => c.enrollment_status === 0);

  return (
    <div className="li-home">
      <div className="li-home__greet">
        <div>
          <h1>Merhaba, {user.firstName}</h1>
          <p>{user.program}</p>
        </div>
        
        {/* Risk Level Tag */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <Tag tone={!hasRisk ? 'amber' : risk.risk_level === 'Düşük' ? 'green' : risk.risk_level === 'Orta' ? 'amber' : 'red'} variant="solid" size="md">
            Akademik Risk: {riskLevelText}
          </Tag>
        </div>
      </div>

      {/* KPI strip using basic_values & basic stats */}
      <div className="li-home__kpis">
        <StatCard
          label="Odak Puanı"
          value={basic.focus_score != null ? `${Math.round(basic.focus_score)}%` : '—'}
          tone="primary"
          delta="12.3%"
          deltaDir="up"
          caption="geçen haftaya göre"
          icon={<span className="material-icons">bolt</span>}
        />
        <StatCard
          label="Not Ortalaması"
          value={basic.gpa != null ? basic.gpa.toFixed(1) : '—'}
          tone="green"
          delta={null}
          caption="dönem ortalaması"
          icon={<span className="material-icons">grade</span>}
        />
        <StatCard
          label="Çalışma Serisi"
          value={basic.streak != null ? `${basic.streak} gün` : '—'}
          tone="gold"
          delta="Aktif"
          deltaDir="up"
          caption="ardışık aktif gün"
          icon={<span className="material-icons">local_fire_department</span>}
        />
        <StatCard
          label="Geciken Ödev"
          value={basic.late_assignments != null ? basic.late_assignments.toString() : '—'}
          tone="red"
          delta={null}
          caption="kalan deadline"
          icon={<span className="material-icons">assignment_late</span>}
        />
      </div>

      {/* Daily activity line - driven by learningPath dataset */}
      <Card
        className="li-home__engagement"
        title="Günlük Çalışma Süresi"
        linkLabel="Detaylı Analize Git"
        hoverable
        onLinkClick={(e) => {
          e.preventDefault();
          onNavigate('learning');
        }}
      >
        <p className="li-card__sub">
          Son 7 gün · Dakika cinsinden günlük çalışma süren <span className="li-src">GET /api/student/me/learning-path</span>
        </p>
        <LineChart
          labels={weekLabels}
          datasets={[{ label: 'Dakika', data: weekMinutes, color: 'var(--primary)' }]}
          height={200}
        />
      </Card>

      {/* Main card grid */}
      <div className="li-home__grid">
        {/* Profile Card */}
        <Card
          className="g-profile"
          title={user.name}
          linkLabel="Profile Git"
          hoverable
          onLinkClick={(e) => {
            e.preventDefault();
            onNavigate('account');
          }}
        >
          <div className="li-profile">
            <Avatar src={user.photo} name={user.name} size="xl" ring />
            <p className="li-profile__meta">{user.program}</p>
          </div>
        </Card>

        {/* Risk Premodel Analysis Card */}
        <Card title="Akademik Risk Değerlendirmesi" linkLabel="Veri Hattına Git" onLinkClick={(e) => { e.preventDefault(); onNavigate('lineage'); }} hoverable>
          <p className="li-card__sub" style={{ margin: '-8px 0 8px 0' }}>
            Yapay zeka başarı olasılığı tahmin modeli <span className="li-src">GET /api/student/me/dashboard</span>
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '10px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '14px', fontWeight: '500', color: 'var(--text-secondary)' }}>Başarı Olasılığı:</span>
              <span className="li-num" style={{ fontSize: '20px', fontWeight: 'bold', color: 'var(--success)' }}>
                {passProbText}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '14px', fontWeight: '500', color: 'var(--text-secondary)' }}>Risk Skoru:</span>
              <span className="li-num" style={{ fontSize: '20px', fontWeight: 'bold', color: (risk && risk.risk_score != null && risk.risk_score > 50) ? 'var(--danger)' : 'var(--primary)' }}>
                {riskScoreText}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '14px', fontWeight: '500', color: 'var(--text-secondary)' }}>Geçme Durumu:</span>
              {!hasRisk ? (
                <Tag tone="amber" variant="soft">Hesaplanıyor</Tag>
              ) : (
                <Tag tone={risk.will_pass ? 'success' : 'danger'} variant="soft">
                  {risk.will_pass ? 'Dersi Geçiyor' : 'Risk Altında'}
                </Tag>
              )}
            </div>
            {risk && risk.recommendations && risk.recommendations.length > 0 && (
              <div style={{ marginTop: '12px', paddingTop: '16px', borderTop: '1px dashed var(--border)' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', display: 'block', marginBottom: '10px' }}>Akıllı Öneriler:</span>
                <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {risk.recommendations.map((rec: string, idx: number) => (
                    <li key={idx}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>

        {/* Grades Chart - driven by apiData.home.courses */}
        <Card
          className="g-grades"
          title="Notlarım"
          linkLabel="Not Detayına Git →"
          hoverable
          onLinkClick={(e) => {
            e.preventDefault();
            onNavigate('grades');
          }}
        >
          <p className="li-card__sub" style={{ margin: '-8px 0 8px 0' }}>
            Normalise edilmiş not ortalamaları <span className="li-src">GET /api/student/me/home</span>
          </p>
          <BarChart
            labels={activeCourses.map((c: any) => c.course_shortname)}
            data={activeCourses.map((c: any) => c.avg_grade)}
            colors={activeCourses.map((c: any) => courseColors[c.courseid] || 'var(--primary)')}
            height={160}
          />
        </Card>

        {/* Mini Calendar Card - driven by events */}
        <Card
          className="g-cal"
          title="Takvim"
          linkLabel="Takvime Git"
          hoverable
          onLinkClick={(e) => {
            e.preventDefault();
            onNavigate('calendar');
          }}
        >
          <MiniCalendar events={events} />
        </Card>

        {/* Activity Breakdown Chart - driven by competencies.activityBreakdown (önizleme) */}
        <Card
          className="g-comp"
          title="Öğrenme Etkinliği"
          linkLabel="Yetkinlik Detayına Git →"
          hoverable
          onLinkClick={(e) => {
            e.preventDefault();
            onNavigate('competencies');
          }}
        >
          <DoughnutChart
            labels={competencies.activityBreakdown.map((a: any) => a.label)}
            data={competencies.activityBreakdown.map((a: any) => a.value)}
            colors={competencies.activityBreakdown.map((a: any) => a.color)}
            height={190}
            legend="right"
          />
        </Card>
      </div>
    </div>
  );
};

import React from 'react';
import { Card, StatCard, Tag } from '../components';
import { LineChart } from '../components/Charts';

interface LearningPathScreenProps {
  apiData: any;
}

const ACTION_TONE: Record<string, 'green' | 'blue' | 'amber' | 'gray'> = {
  Submit: 'green',
  View: 'blue',
};

export const LearningPathScreen: React.FC<LearningPathScreenProps> = ({ apiData }) => {
  const lp = apiData.learningPath || {};
  const dataset: any[] = lp.dataset || [];
  const timeline: any[] = lp.timeline || [];

  // Günlük seri → tarih etiketleri "DD.MM"
  const labels = dataset.map((d: any) => {
    const p = String(d.activity_date || '').split('-');
    return p.length === 3 ? `${p[2]}.${p[1]}` : String(d.activity_date || '');
  });
  const minutes = dataset.map((d: any) => d.total_minutes || 0);
  const sessions = dataset.map((d: any) => d.session_count || 0);

  const totalMin = Math.round(minutes.reduce((a: number, b: number) => a + b, 0));
  const totalSes = sessions.reduce((a: number, b: number) => a + b, 0);
  const activeDays = dataset.filter((d: any) => (d.total_minutes || 0) > 0).length;

  return (
    <div className="li-page">
      <div className="li-page__head">
        <div>
          <h1>Öğrenme Patikası</h1>
          <p>Günlük çalışma temposu ve son aktivite akışı</p>
        </div>
      </div>

      {/* KPI şeridi */}
      <div className="li-home__kpis" style={{ marginBottom: 16 }}>
        <StatCard label="Toplam Süre" value={`${totalMin} dk`} tone="primary"
          icon={<span className="material-icons">schedule</span>} />
        <StatCard label="Toplam Oturum" value={totalSes.toString()} tone="green"
          icon={<span className="material-icons">login</span>} />
        <StatCard label="Aktif Gün" value={activeDays.toString()} tone="gold"
          icon={<span className="material-icons">event_available</span>} />
      </div>

      {/* Günlük çalışma grafiği */}
      <Card title="Günlük Çalışma Süresi & Oturum">
        <p className="li-card__sub">
          Tarihe göre dakika ve oturum sayısı <span className="li-src">GET /api/student/me/learning-path</span>
        </p>
        {dataset.length > 0 ? (
          <LineChart
            labels={labels}
            datasets={[
              { label: 'Dakika', data: minutes, color: 'var(--primary)' },
              { label: 'Oturum', data: sessions, color: 'var(--cat-amber)' },
            ]}
            height={260}
          />
        ) : (
          <p className="li-card__sub">Bu öğrenci için günlük aktivite verisi bulunamadı.</p>
        )}
      </Card>

      {/* Aktivite timeline */}
      <Card title="Son Aktiviteler" className="li-agenda">
        <p className="li-card__sub">
          Modül tamamlama / görüntüleme akışı <span className="li-src">GET /api/student/me/learning-path</span>
        </p>
        {timeline.length > 0 ? (
          <ul className="li-agenda__list">
            {timeline.slice(0, 30).map((t: any, i: number) => (
              <li key={i} className="li-agenda__item">
                <span className="li-agenda__dot"
                  style={{ background: t.action === 'Submit' ? 'var(--success)' : 'var(--primary)' }}></span>
                <div className="li-agenda__body">
                  <div className="li-agenda__title">{t.title}</div>
                  <div className="li-agenda__meta">{t.date}</div>
                </div>
                <Tag tone={ACTION_TONE[t.action] || 'gray'} variant="soft" size="sm">
                  {t.action === 'Submit' ? 'Tamamlandı' : 'Görüntülendi'}
                </Tag>
              </li>
            ))}
          </ul>
        ) : (
          <p className="li-card__sub">Henüz aktivite kaydı yok.</p>
        )}
      </Card>
    </div>
  );
};

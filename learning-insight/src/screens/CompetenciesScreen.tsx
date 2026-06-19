import React from 'react';
import { Card, Tag } from '../components';
import { RadarChart, DoughnutChart } from '../components/Charts';

interface CompetenciesScreenProps {
  apiData: {
    competencies: {
      competencies: Array<{
        name: string;
        value: number;
        framework: string;
      }>;
      activityBreakdown: Array<{
        label: string;
        moodle: string;
        value: number;
        color: string;
      }>;
      completionByCourse: Array<{
        course: string;
        completed: number;
        total: number;
      }>;
    };
  };
}

function profLabel(v: number): { text: string; tone: string } {
  if (v >= 85) return { text: 'İleri Seviye', tone: 'green' };
  if (v >= 70) return { text: 'Yeterli', tone: 'sky' };
  if (v >= 50) return { text: 'Gelişmekte', tone: 'amber' };
  return { text: 'Başlangıç', tone: 'red' };
}

export const CompetenciesScreen: React.FC<CompetenciesScreenProps> = ({ apiData }) => {
  const compData = apiData.competencies;
  const competenciesList = compData.competencies || [];
  const breakdownList = compData.activityBreakdown || [];
  const completionList = compData.completionByCourse || [];

  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>Yetkinlikler</h1>
        <p>Yetkinlik çerçevesi ve öğrenme etkinliği dağılımı</p>
      </div>

      <div className="li-grades__charts">
        <Card title="Yetkinlik Profili">
          <p className="li-card__sub">
            Ustalık seviyesi 0–100 <span className="li-src">mdl_competency_usercomp</span>
          </p>
          <RadarChart
            labels={competenciesList.map((c) => c.name)}
            data={competenciesList.map((c) => c.value)}
            height={280}
          />
        </Card>

        <Card title="Öğrenme Etkinliği Dağılımı">
          <p className="li-card__sub">
            Etkinlik türüne göre çalışma dağılımı (%) <span className="li-src">mdl_modules + log</span>
          </p>
          <DoughnutChart
            labels={breakdownList.map((a) => a.label)}
            data={breakdownList.map((a) => a.value)}
            colors={breakdownList.map((a) => a.color)}
            height={280}
            legend="right"
          />
        </Card>
      </div>

      <div className="li-grades__charts">
        <Card title="Yetkinlik Çerçevesi">
          <p className="li-card__sub">
            Tanımlı akademik yetkinlikler <span className="li-src">mdl_competency</span>
          </p>
          <div className="li-tablewrap">
            <table className="li-table">
              <thead>
                <tr>
                  <th>Yetkinlik</th>
                  <th>Çerçeve</th>
                  <th className="ta-r">Seviye</th>
                  <th>İlerleme</th>
                  <th className="ta-c">Durum</th>
                </tr>
              </thead>
              <tbody>
                {competenciesList.map((c, i) => {
                  const p = profLabel(c.value);
                  return (
                    <tr key={i}>
                      <td className="li-table__name">{c.name}</td>
                      <td className="li-table__muted">{c.framework}</td>
                      <td className="ta-r li-num li-table__grade">{c.value}</td>
                      <td>
                        <div className="li-table__bar">
                          <span style={{ width: `${c.value}%`, background: 'var(--primary)' }}></span>
                        </div>
                      </td>
                      <td className="ta-c">
                        <Tag tone={p.tone} variant="soft" size="sm">
                          {p.text}
                        </Tag>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Aktivite Tamamlama Oranları">
          <p className="li-card__sub">
            Ders bazlı tamamlanan etkinlikler <span className="li-src">mdl_course_modules_completion</span>
          </p>
          <div className="li-completion" style={{ padding: '8px 0' }}>
            {completionList.map((c, i) => {
              const pct = c.total > 0 ? Math.round((c.completed / c.total) * 100) : 0;
              return (
                <div className="li-completion__row" key={i} style={{ marginBottom: '16px' }}>
                  <div className="li-completion__top" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span className="li-completion__name" style={{ fontWeight: 'semibold' }}>{c.course}</span>
                    <span className="li-num li-completion__val">
                      {c.completed}/{c.total} · %{pct}
                    </span>
                  </div>
                  <div className="li-table__bar" style={{ width: '100%' }}>
                    <span
                      style={{
                        width: `${pct}%`,
                        background:
                          pct >= 80
                            ? 'var(--success)'
                            : pct >= 50
                            ? 'var(--cat-amber)'
                            : 'var(--danger)',
                      }}
                    ></span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
};


import React, { useState } from 'react';
import { Card, StatCard } from '../components';
import type { ActivityHeatmap } from '../data/mockData';

interface ActivityHeatmapScreenProps {
  apiData: {
    heatmap: ActivityHeatmap[];
  };
}

const DAYS = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'];

export const ActivityHeatmapScreen: React.FC<ActivityHeatmapScreenProps> = ({ apiData }) => {
  const [selectedCell, setSelectedCell] = useState<{ day: number; hour: number; events: number; starts: number } | null>(null);

  const heatmapData = apiData.heatmap || [];

  // Group heatmap data into 2D array [day][hour]
  const grid: ActivityHeatmap[][] = Array.from({ length: 7 }, () => []);
  
  heatmapData.forEach((cell) => {
    // weekday is 0-6
    if (cell.weekday >= 0 && cell.weekday < 7) {
      grid[cell.weekday][cell.hour] = cell;
    }
  });

  // Find max event count for color normalization
  const maxEvents = Math.max(...heatmapData.map((c) => c.event_count), 1);

  // Calculate high-level stats from dash_06
  const totalEvents = heatmapData.reduce((sum, c) => sum + c.event_count, 0);
  const totalSessions = heatmapData.reduce((sum, c) => sum + c.session_starts, 0);
  
  // Find peak hour
  let peakHour = 0;
  let maxHourEvents = 0;
  const hourSums = Array(24).fill(0);
  heatmapData.forEach((c) => {
    hourSums[c.hour] += c.event_count;
  });
  hourSums.forEach((sum, hr) => {
    if (sum > maxHourEvents) {
      maxHourEvents = sum;
      peakHour = hr;
    }
  });

  // Calculate cell color based on intensity
  const getCellColor = (events: number) => {
    if (events === 0) return 'var(--neutral-100)';
    const intensity = events / maxEvents;
    // Mix sky blue (#74BBE3) and brand navy (#1B5FA8)
    return `rgba(27, 95, 168, ${Math.max(0.1, intensity * 0.9)})`;
  };

  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>Çalışma Isı Haritası</h1>
        <p>Haftalık ve saatlik bazda Moodle log etkinlik yoğunluğu</p>
      </div>

      <div className="li-home__kpis li-home__kpis--3" style={{ marginBottom: '24px' }}>
        <StatCard
          label="Toplam Log Event"
          value={totalEvents.toString()}
          tone="primary"
          caption="Moodle log kayıtları"
          icon={<span className="material-icons">query_stats</span>}
        />
        <StatCard
          label="Yeni Oturum Başlangıcı"
          value={totalSessions.toString()}
          tone="green"
          caption="30dk boşluk kuralı ile"
          icon={<span className="material-icons">login</span>}
        />
        <StatCard
          label="En Aktif Saat"
          value={`${peakHour.toString().padStart(2, '0')}:00`}
          tone="gold"
          caption={`Peak: ${maxHourEvents} toplam event`}
          icon={<span className="material-icons">wb_sunny</span>}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        <Card title="Aktivite Isı Matrisi (7 Gün × 24 Saat)">
          <p className="li-card__sub" style={{ margin: '-8px 0 16px 0' }}>
            Hücrelerin üzerine tıklayarak detaylı event ve oturum sayılarını inceleyebilirsin <span className="li-src">dash_06_activity_heatmap.csv</span>
          </p>

          <div style={{ overflowX: 'auto', padding: '10px 0' }}>
            <div style={{ minWidth: '800px' }}>
              {/* Hour Header */}
              <div style={{ display: 'flex', marginBottom: '8px' }}>
                <div style={{ width: '100px', flexShrink: 0 }}></div>
                <div style={{ display: 'flex', flex: 1, justifyContent: 'space-between' }}>
                  {Array.from({ length: 24 }).map((_, hr) => (
                    <span
                      key={hr}
                      className="li-num"
                      style={{
                        width: '100%',
                        textAlign: 'center',
                        fontSize: '11px',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {hr}
                    </span>
                  ))}
                </div>
              </div>

              {/* Grid Rows */}
              {DAYS.map((dayName, dayIdx) => (
                <div key={dayIdx} style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                  <div
                    style={{
                      width: '100px',
                      fontSize: '12px',
                      fontWeight: 'bold',
                      color: 'var(--text-primary)',
                      flexShrink: 0,
                    }}
                  >
                    {dayName}
                  </div>
                  <div style={{ display: 'flex', flex: 1, gap: '4px' }}>
                    {Array.from({ length: 24 }).map((_, hr) => {
                      const cell = grid[dayIdx][hr] || { event_count: 0, session_starts: 0 };
                      const isSelected = selectedCell?.day === dayIdx && selectedCell?.hour === hr;
                      
                      return (
                        <div
                          key={hr}
                          onClick={() =>
                            setSelectedCell({
                              day: dayIdx,
                              hour: hr,
                              events: cell.event_count,
                              starts: cell.session_starts,
                            })
                          }
                          style={{
                            width: '100%',
                            aspectRatio: '1.2',
                            backgroundColor: getCellColor(cell.event_count),
                            borderRadius: '4px',
                            cursor: 'pointer',
                            transition: 'transform 0.1s ease',
                            border: isSelected ? '2px solid var(--primary)' : '1px solid rgba(0,0,0,0.05)',
                            transform: isSelected ? 'scale(1.15)' : 'none',
                            boxShadow: isSelected ? 'var(--shadow-md)' : 'none',
                          }}
                          title={`${dayName} saat ${hr}:00 · ${cell.event_count} event`}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '16px',
              borderTop: '1px solid var(--border-subtle)',
              paddingTop: '16px',
            }}
          >
            {/* Color Legend */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <span>Düşük</span>
              <div style={{ display: 'flex', gap: '2px' }}>
                <div style={{ width: '16px', height: '16px', backgroundColor: 'var(--neutral-100)', borderRadius: '3px' }}></div>
                <div style={{ width: '16px', height: '16px', backgroundColor: 'rgba(27, 95, 168, 0.2)', borderRadius: '3px' }}></div>
                <div style={{ width: '16px', height: '16px', backgroundColor: 'rgba(27, 95, 168, 0.4)', borderRadius: '3px' }}></div>
                <div style={{ width: '16px', height: '16px', backgroundColor: 'rgba(27, 95, 168, 0.6)', borderRadius: '3px' }}></div>
                <div style={{ width: '16px', height: '16px', backgroundColor: 'rgba(27, 95, 168, 0.9)', borderRadius: '3px' }}></div>
              </div>
              <span>Yüksek Yoğunluk</span>
            </div>

            {/* Selection HUD */}
            {selectedCell ? (
              <div
                style={{
                  fontSize: '13px',
                  backgroundColor: 'var(--blue-50)',
                  color: 'var(--blue-800)',
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: '500',
                }}
              >
                {DAYS[selectedCell.day]} {selectedCell.hour.toString().padStart(2, '0')}:00 - {selectedCell.events} log olayı, {selectedCell.starts} oturum başlangıcı
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--text-disabled)' }}>
                Detaylar için ısı matrisinden bir hücreye tıkla.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};


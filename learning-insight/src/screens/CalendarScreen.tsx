import React, { useState } from 'react';
import { Card, Tag } from '../components';

// 2. AcademicEvent (Veri Modeli / Data Structure)
export interface AcademicEvent {
  userid: number;
  courseid: number;
  cmid: number;
  module_type: string;
  display_name: string;
  course_name: string;
  course_short: string;
  event_date: string; // YYYY-MM-DD
  timestart: number;
  days_until: number;
  is_overdue: boolean;
  is_completed: boolean;
}

// 3. EventProcessor (Mantık İşleyici / Logic Helper)
export class EventProcessor {
  private todayStr: string;

  constructor(todayStr: string = '2026-06-15') {
    this.todayStr = todayStr;
  }

  // a. isUpcoming(date): (Bugün - 7 gün) <= date
  public isUpcoming(dateStr: string): boolean {
    const today = new Date(this.todayStr);
    const date = new Date(dateStr);
    const limit = new Date(today);
    limit.setDate(today.getDate() - 7);
    return limit <= date;
  }

  // b. isPast(date): date <= (Bugün + 7 gün)
  public isPast(dateStr: string): boolean {
    const today = new Date(this.todayStr);
    const date = new Date(dateStr);
    const limit = new Date(today);
    limit.setDate(today.getDate() + 7);
    return date <= limit;
  }

  // classify(events): "Geçmiş", "Yaklaşan", "Gelecek" olarak 3 ayrı diziye ayırır
  public classify(events: AcademicEvent[]) {
    const past: AcademicEvent[] = [];
    const upcoming: AcademicEvent[] = [];
    const future: AcademicEvent[] = [];

    const today = new Date(this.todayStr);

    events.forEach((event) => {
      const eventDate = new Date(event.event_date);
      if (event.is_completed || eventDate < today) {
        past.push(event);
      } else if (this.isUpcoming(event.event_date) && eventDate >= today) {
        upcoming.push(event);
      } else {
        future.push(event);
      }
    });

    return { past, upcoming, future };
  }
}

const EVT_META: Record<string, { tone: string; label: string; color: string }> = {
  today: { tone: 'primary', label: 'Bugün', color: 'var(--primary)' },
  overdue: { tone: 'danger', label: 'Gecikmiş', color: 'var(--danger)' },
  upcoming: { tone: 'warning', label: 'Yaklaşan', color: 'var(--cat-amber)' },
  completed: { tone: 'green', label: 'Tamamlandı', color: 'var(--success)' },
};

interface EventCardProps {
  event: AcademicEvent;
  type: string;
}

// 4. EventCard (Kutucuk Bileşeni / UI Component)
export const EventCard: React.FC<EventCardProps> = ({ event, type }) => {
  // b. getColorByType(type): Kutucuğu etkinlik türüne göre renklendirir
  const getColorByType = (t: string): string => {
    return EVT_META[t]?.color || 'var(--primary)';
  };

  const meta = EVT_META[type] || EVT_META.upcoming;
  const color = getColorByType(type);

  // a. renderLayout(): Bu metodla sayfadaki her bir event(etkinlik) için kutucuk oluşmasını sağlar
  const renderLayout = () => {
    const day = parseInt(event.event_date.split('-')[2], 10);
    let timeLabel = `${day} Haziran`;
    if (type === 'today') timeLabel = 'Bugün';

    return (
      <li className="li-agenda__item">
        <span className="li-agenda__dot" style={{ background: color }}></span>
        <div className="li-agenda__body">
          <div className="li-agenda__title">
            {event.course_short} — {event.display_name}
          </div>
          <div className="li-agenda__meta li-num">
            {timeLabel} · {event.days_until < 0 ? `${Math.abs(event.days_until)} gün gecikti` : event.days_until === 0 ? 'Bugün teslim' : `${event.days_until} gün kaldı`}
          </div>
        </div>
        <Tag tone={meta.tone} variant="soft" size="sm">
          {meta.label}
        </Tag>
      </li>
    );
  };

  return renderLayout();
};

interface CalendarPageProps {
  apiData: any;
}

const MONTH_NAMES = [
  'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'
];

// 1. CalendarPage (Ana Sayfa / Container)
export const CalendarPage: React.FC<CalendarPageProps> = ({ apiData }) => {
  const eventsList: AcademicEvent[] = apiData.events || [];
  const dows = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];
  
  // State for month and year navigation
  const [currentMonth, setCurrentMonth] = useState<number>(5); // June (index 5)
  const [currentYear, setCurrentYear] = useState<number>(2026);
  
  const today = 15; // Simulated today's day in June 2026
  
  const handlePrevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  // Filter events belonging to current month and year
  const activeMonthEvents = eventsList.filter((e) => {
    const d = new Date(e.event_date);
    return d.getMonth() === currentMonth && d.getFullYear() === currentYear;
  });

  // Sort events by date ascending
  const sortedEvents = [...activeMonthEvents].sort(
    (a, b) => new Date(a.event_date).getTime() - new Date(b.event_date).getTime()
  );

  // Group events by day of month
  const byDay = activeMonthEvents.reduce((acc: any, event: AcademicEvent) => {
    const day = parseInt(event.event_date.split('-')[2], 10);
    if (!isNaN(day)) {
      acc[day] = acc[day] || [];
      acc[day].push(event);
    }
    return acc;
  }, {} as Record<number, AcademicEvent[]>);

  // Calculate dynamic cells
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const offset = new Date(currentYear, currentMonth, 1).getDay();
  // Monday start offset calculation
  const startOffset = offset === 0 ? 6 : offset - 1;

  const cells: (number | null)[] = [];
  for (let i = 0; i < startOffset; i++) {
    cells.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(d);
  }

  const getEventType = (e: AcademicEvent, day: number) => {
    if (e.is_completed) return 'completed';
    if (day === today && currentMonth === 5 && currentYear === 2026) return 'today';
    if (e.is_overdue) return 'overdue';
    return 'upcoming';
  };

  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>Takvim</h1>
        <p>{MONTH_NAMES[currentMonth]} {currentYear} · Ders, sınav ve teslim tarihleri</p>
      </div>

      <div className="li-callayout">
        {/* Main Month Calendar Card */}
        <Card className="li-calmain">
          <div className="li-calmain__head">
            <span className="material-icons li-calmain__nav" onClick={handlePrevMonth} style={{ cursor: 'pointer' }}>
              chevron_left
            </span>
            <h2>{MONTH_NAMES[currentMonth]} {currentYear}</h2>
            <span className="material-icons li-calmain__nav" onClick={handleNextMonth} style={{ cursor: 'pointer' }}>
              chevron_right
            </span>
          </div>
          <div className="li-calfull">
            {dows.map((d) => (
              <span key={d} className="li-calfull__dow">
                {d}
              </span>
            ))}
            {cells.map((d, i) => {
              const isTodayCell = d === today && currentMonth === 5 && currentYear === 2026;
              return (
                <div
                  key={i}
                  className={`li-calfull__cell ${isTodayCell ? 'is-today' : ''} ${
                    !d ? 'is-empty' : ''
                  }`}
                >
                  {d ? <span className="li-calfull__num li-num">{d}</span> : null}
                  {d && byDay[d]
                    ? byDay[d].map((e: AcademicEvent, j: number) => {
                        const type = getEventType(e, d);
                        const meta = EVT_META[type];
                        return (
                          <span
                            key={j}
                            className="li-calfull__evt"
                            style={{
                              background: `color-mix(in srgb, ${meta.color} 16%, white)`,
                              color: meta.color,
                            }}
                            title={`${e.course_short}: ${e.display_name}`}
                          >
                            {e.display_name}
                          </span>
                        );
                      })
                    : null}
                </div>
              );
            })}
          </div>
        </Card>

        {/* Agenda Card listing Month Events via EventCard */}
        <Card title="Yaklaşan Etkinlikler" className="li-agenda">
          <p className="li-card__sub" style={{ margin: '-8px 0 12px 0' }}>
            Deadlinelar ve durumları <span className="li-src">GET /api/student/me/events</span>
          </p>
          <ul className="li-agenda__list">
            {sortedEvents.map((e: AcademicEvent, i: number) => {
              const day = parseInt(e.event_date.split('-')[2], 10);
              const type = getEventType(e, day);
              
              return (
                <EventCard
                  key={i}
                  event={e}
                  type={type}
                />
              );
            })}
            {sortedEvents.length === 0 && (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-disabled)' }}>
                Bu ay için planlanmış etkinlik bulunmuyor.
              </div>
            )}
          </ul>
        </Card>
      </div>
    </div>
  );
};

// Export alias to maintain compatibility with App.tsx imports
export { CalendarPage as CalendarScreen };


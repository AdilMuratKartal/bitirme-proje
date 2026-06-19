import React, { useState } from 'react';
import { Button, Card, ProgressRing, Tag } from '../components';
import { courseColors, courseInstructors } from '../data/mockData';

interface CoursesScreenProps {
  onNavigate: (page: string) => void;
  onSelectCourse: (courseId: number) => void;
  apiData: any;
}

const STATUS_META = {
  active: { label: 'Devam ediyor', tone: 'green' },
  done: { label: 'Tamamlandı', tone: 'emerald' },
  expired: { label: 'Süresi doldu', tone: 'danger' },
};

export const CoursesScreen: React.FC<CoursesScreenProps> = ({ onNavigate, onSelectCourse, apiData }) => {
  const [filter, setFilter] = useState<'all' | 'active' | 'done' | 'expired'>('active');
  
  const rawCourses = apiData.home.courses || [];

  const courseList = rawCourses.map((c: any) => {
    let status: 'active' | 'done' | 'expired' = 'active';
    if (c.enrollment_status === 1) status = 'expired';
    else if (c.completion_pct === 100) status = 'done';
    return { ...c, status };
  });

  const filtered = courseList.filter((c: any) => {
    if (filter === 'all') return true;
    return c.status === filter;
  });

  const activeCount = courseList.filter((c: any) => c.status === 'active').length;

  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>Kurslarım</h1>
        <p>
          {courseList.length} kurs · {activeCount} tanesi aktif
        </p>
      </div>

      <div className="li-filters">
        <Button
          variant={filter === 'active' ? 'primary' : 'secondary'}
          pill
          onClick={() => setFilter('active')}
        >
          Devam Eden Kurslar
        </Button>
        <Button
          variant={filter === 'expired' ? 'danger' : 'secondary'}
          pill
          onClick={() => setFilter('expired')}
        >
          Süresi Dolan Kurslar
        </Button>
        <Button
          variant={filter === 'done' ? 'success' : 'secondary'}
          pill
          onClick={() => setFilter('done')}
        >
          Biten Kurslar
        </Button>
        <Button
          variant={filter === 'all' ? 'primary' : 'ghost'}
          pill
          onClick={() => setFilter('all')}
        >
          Tümü
        </Button>
      </div>

      <div className="li-coursegrid">
        {filtered.map((c: any) => {
          const s = STATUS_META[c.status as keyof typeof STATUS_META] || STATUS_META.active;
          const color = courseColors[c.courseid] || 'var(--primary)';
          const instructor = courseInstructors[c.courseid] || 'Bilinmiyor';
          const deadlineText = c.next_expected_date
            ? `Sıradaki: ${c.next_expected_date}`
            : 'Planlı aktivite yok';

          return (
            <Card key={c.courseid} hoverable className="li-coursecard">
              <div className="li-coursecard__top">
                <div>
                  <div className="li-coursecard__code li-num">{c.course_shortname}</div>
                  <div className="li-coursecard__name">{c.course_fullname}</div>
                </div>
                <Tag tone={s.tone} variant="soft">
                  {s.label}
                </Tag>
              </div>
              <div className="li-coursecard__ring">
                <ProgressRing
                  value={c.completion_pct}
                  size={132}
                  variant="semi"
                  color={color}
                  label="Tamamlama"
                />
              </div>
              <div className="li-coursecard__foot">
                <span className="li-coursecard__meta">
                  <span className="material-icons">person</span>
                  {instructor}
                </span>
                <span className="li-coursecard__meta">
                  <span className="material-icons">event</span>
                  {deadlineText}
                </span>
              </div>
              <a
                className="li-coursecard__link"
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  onSelectCourse(c.courseid);
                  onNavigate('coursedetail');
                }}
              >
                Detaya git<span className="material-icons">chevron_right</span>
              </a>
            </Card>
          );
        })}
      </div>
    </div>
  );
};

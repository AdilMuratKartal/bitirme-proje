import React from 'react';
import { NavItem } from './index';

interface SidebarProps {
  page: string;
  onNavigate: (page: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}

const sidebarNav = [
  { key: 'home', icon: 'home', label: 'Home' },
  { key: 'courses', icon: 'menu_book', label: 'Kurslarım' },
  { key: 'grades', icon: 'grade', label: 'Grades' },
  { key: 'calendar', icon: 'calendar_month', label: 'Calendar' },
  { key: 'heatmap', icon: 'grid_on', label: 'Isı Haritası' },
  { key: 'certificates', icon: 'workspace_premium', label: 'Certificates' },
  { key: 'competencies', icon: 'psychology', label: 'Competencies' },
  { key: 'learning', icon: 'route', label: 'Learning Path' },
  { key: 'lineage', icon: 'dns', label: 'Veri Hattı' },
];

export const Sidebar: React.FC<SidebarProps> = ({ page, onNavigate, collapsed }) => {
  return (
    <aside className="li-sidebar" style={{ width: collapsed ? 83 : 250 }}>
      <nav className="li-sidebar__list">
        {sidebarNav.map((item) => (
          <NavItem
            key={item.key}
            icon={item.icon}
            label={item.label}
            collapsed={collapsed}
            selected={page === item.key || (item.key === 'courses' && page === 'coursedetail')}
            onClick={() => onNavigate(item.key)}
          />
        ))}
      </nav>
    </aside>
  );
};

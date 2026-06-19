import React from 'react';
import { injectOnce } from './inject';

const CSS = `
@keyframes li-pulse {
  0% { background-color: var(--neutral-200); }
  50% { background-color: var(--neutral-100); }
  100% { background-color: var(--neutral-200); }
}
.li-sk-pulse {
  animation: li-pulse 1.5s infinite ease-in-out;
}
.li-sk-block {
  background: var(--neutral-200);
  border-radius: var(--radius-sm);
}
.li-sk-circle {
  border-radius: var(--radius-circle);
}
.li-sk-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--space-4);
  box-sizing: border-box;
}
.li-sk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.li-sk-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.li-sk-kpi {
  background: var(--surface-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  height: 90px;
  box-sizing: border-box;
}
.li-sk-chart-wide {
  background: var(--surface-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-4);
  height: 250px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  box-sizing: border-box;
}
.li-sk-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-5);
}
.li-sk-card {
  background: var(--surface-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: var(--space-4);
  height: 230px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  box-sizing: border-box;
}
@media (max-width: 1100px) {
  .li-sk-kpis { grid-template-columns: repeat(2, 1fr); }
  .li-sk-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 720px) {
  .li-sk-kpis { grid-template-columns: 1fr; }
  .li-sk-grid { grid-template-columns: 1fr; }
}
`;

export const Skeleton: React.FC = () => {
  injectOnce('li-skeleton-styles', CSS);

  return (
    <div className="li-sk-container">
      {/* Header Greet Skeleton */}
      <div className="li-sk-header">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div className="li-sk-block li-sk-pulse" style={{ width: '180px', height: '28px' }}></div>
          <div className="li-sk-block li-sk-pulse" style={{ width: '260px', height: '18px' }}></div>
        </div>
        <div className="li-sk-block li-sk-pulse" style={{ width: '220px', height: '44px', borderRadius: '12px' }}></div>
      </div>

      {/* KPI strip Skeleton */}
      <div className="li-sk-kpis">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="li-sk-kpi">
            <div className="li-sk-block li-sk-pulse" style={{ width: '44px', height: '44px' }}></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
              <div className="li-sk-block li-sk-pulse" style={{ width: '50%', height: '14px' }}></div>
              <div className="li-sk-block li-sk-pulse" style={{ width: '80%', height: '22px' }}></div>
            </div>
          </div>
        ))}
      </div>

      {/* Chart Skeleton */}
      <div className="li-sk-chart-wide">
        <div className="li-sk-block li-sk-pulse" style={{ width: '200px', height: '22px' }}></div>
        <div className="li-sk-block li-sk-pulse" style={{ width: '100%', flex: 1 }}></div>
      </div>

      {/* Cards Grid Skeleton */}
      <div className="li-sk-grid">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="li-sk-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="li-sk-block li-sk-pulse" style={{ width: '100px', height: '20px' }}></div>
              <div className="li-sk-block li-sk-pulse" style={{ width: '60px', height: '16px' }}></div>
            </div>
            <div className="li-sk-block li-sk-pulse" style={{ width: '100%', flex: 1 }}></div>
          </div>
        ))}
      </div>
    </div>
  );
};
export default Skeleton;

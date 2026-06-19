import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-stat{background:var(--surface-card);border-radius:var(--radius-md);box-shadow:var(--shadow-sm);padding:var(--space-4) var(--space-5);display:flex;align-items:flex-start;gap:var(--space-4);font-family:var(--font-sans);text-align:left;}
.li-stat__icon{width:44px;height:44px;border-radius:var(--radius-sm);flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:24px;background:var(--stat-soft);color:var(--stat-color);}
.li-stat__main{display:flex;flex-direction:column;gap:2px;min-width:0;text-align:left;}
.li-stat__label{font-size:var(--text-sm);color:var(--text-secondary);font-weight:var(--weight-medium);text-align:left;}
.li-stat__value{font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-size:var(--text-3xl);font-weight:var(--weight-bold);line-height:1.05;color:var(--text-primary);text-align:left;}
.li-stat__row{display:flex;align-items:center;gap:6px;margin-top:2px;text-align:left;}
.li-stat__delta{display:inline-flex;align-items:center;gap:2px;font-size:var(--text-xs);font-weight:var(--weight-bold);font-variant-numeric:tabular-nums;}
.li-stat__delta .material-icons{font-size:14px;}
.li-stat__delta--up{color:var(--success);}.li-stat__delta--down{color:var(--danger);}.li-stat__delta--flat{color:var(--text-secondary);}
.li-stat__caption{font-size:var(--text-xs);color:var(--text-secondary);text-align:left;}
`;

const STAT_TONE = {
  primary: ['var(--primary)', 'var(--blue-50)'],
  green: ['var(--cat-green)', 'var(--success-bg)'],
  gold: ['var(--gold-600)', 'var(--warning-bg)'],
  red: ['var(--danger)', 'var(--danger-bg)'],
  purple: ['var(--cat-purple)', '#F3E6F3'],
  sky: ['var(--cat-sky)', 'var(--blue-50)'],
};

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  tone?: 'primary' | 'green' | 'gold' | 'red' | 'purple' | 'sky';
  delta?: string | number | null;
  deltaDir?: 'up' | 'down' | 'flat';
  caption?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  icon = null,
  tone = 'primary',
  delta = null,
  deltaDir = 'up',
  caption,
  className = '',
  style = {},
  ...rest
}) => {
  injectOnce('li-statcard-styles', CSS);

  const [color, soft] = STAT_TONE[tone] || STAT_TONE.primary;
  const di = deltaDir === 'up' ? 'arrow_upward' : deltaDir === 'down' ? 'arrow_downward' : 'remove';

  return (
    <div
      className={`li-stat ${className}`}
      style={{ '--stat-color': color, '--stat-soft': soft, ...style } as React.CSSProperties}
      {...rest}
    >
      {icon ? <div className="li-stat__icon">{icon}</div> : null}
      <div className="li-stat__main">
        <span className="li-stat__label">{label}</span>
        <span className="li-stat__value">{value}</span>
        <div className="li-stat__row">
          {delta !== null && delta !== undefined ? (
            <span className={`li-stat__delta li-stat__delta--${deltaDir}`}>
              <span className="material-icons">{di}</span>
              {delta}
            </span>
          ) : null}
          {caption ? <span className="li-stat__caption">{caption}</span> : null}
        </div>
      </div>
    </div>
  );
};

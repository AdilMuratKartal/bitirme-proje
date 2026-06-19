import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-ring{position:relative;display:inline-flex;align-items:center;justify-content:center;font-family:var(--font-sans);}
.li-ring svg{display:block;transform:rotate(-90deg);}
.li-ring--semi svg{transform:rotate(135deg);}
.li-ring__arc{transition:stroke-dashoffset var(--dur-slow) var(--ease-emphasis);}
.li-ring__center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;}
.li-ring--semi .li-ring__center{inset:auto 0 14%;}
.li-ring__value{font-family:var(--font-mono);font-variant-numeric:tabular-nums;font-weight:var(--weight-bold);line-height:1;}
.li-ring__label{font-size:var(--text-xs);color:var(--text-secondary);font-weight:var(--weight-medium);}
`;

export interface ProgressRingProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
  size?: number;
  thickness?: number;
  variant?: 'circle' | 'semi';
  color?: string;
  trackColor?: string;
  label?: string;
  showValue?: boolean;
  valueSuffix?: string;
}

export const ProgressRing: React.FC<ProgressRingProps> = ({
  value = 0,
  size = 120,
  thickness = 12,
  variant = 'circle',
  color = 'var(--primary)',
  trackColor = 'var(--neutral-200)',
  label,
  showValue = true,
  valueSuffix = '%',
  className = '',
  style = {},
  ...rest
}) => {
  injectOnce('li-ring-styles', CSS);

  const pct = Math.max(0, Math.min(100, value));
  const r = (size - thickness) / 2;
  const circ = 2 * Math.PI * r;
  const portion = variant === 'semi' ? 0.75 : 1;
  const arcLen = circ * portion;
  const offset = arcLen * (1 - pct / 100);
  const vf = Math.round(size * 0.22);

  const containerHeight = variant === 'semi' ? size * 0.78 : size;

  return (
    <div
      className={`li-ring li-ring--${variant} ${className}`}
      style={{ width: size, height: containerHeight, ...style }}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      {...rest}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={trackColor}
          strokeWidth={thickness}
          strokeDasharray={`${arcLen} ${circ}`}
          strokeLinecap="round"
        />
        <circle
          className="li-ring__arc"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeDasharray={`${arcLen} ${circ}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <div className="li-ring__center">
        {showValue ? (
          <span className="li-ring__value" style={{ fontSize: vf, color }}>
            {Math.round(pct)}
            {valueSuffix}
          </span>
        ) : null}
        {label ? <span className="li-ring__label">{label}</span> : null}
      </div>
    </div>
  );
};

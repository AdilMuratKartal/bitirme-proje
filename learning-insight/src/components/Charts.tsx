import React, { useRef, useEffect } from 'react';
import Chart from 'chart.js/auto';

const rootCss = () => (typeof document !== 'undefined' ? getComputedStyle(document.documentElement) : null);

// Resolve color strings (like var(--primary) or hex)
function resolve(c: string): string {
  if (typeof c !== 'string') return c;
  let name = null;
  const m = c.match(/var\((--[\w-]+)\)/);
  if (m) name = m[1]; else if (c.startsWith('--')) name = c;
  if (name) {
    const css = rootCss();
    if (css) return css.getPropertyValue(name).trim() || c;
  }
  return c;
}

// Add opacity to hex color
function alpha(c: string, a: number): string {
  const hex = resolve(c);
  if (/^#([0-9a-f]{6})$/i.test(hex)) {
    return hex + Math.round(a * 255).toString(16).padStart(2, '0');
  }
  return hex;
}

let themed = false;
function applyTheme() {
  if (themed) return;
  themed = true;
  const css = rootCss();
  if (!css) return;

  Chart.defaults.font.family = "'Plus Jakarta Sans', system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = css.getPropertyValue('--text-secondary').trim() || '#6C757D';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.padding = 14;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = css.getPropertyValue('--neutral-900').trim() || '#222';
  Chart.defaults.plugins.tooltip.titleFont = { family: "'Plus Jakarta Sans'", weight: 'bold' };
}

const GRID = 'rgba(20,30,50,0.07)';

interface ChartjsProps {
  type: 'line' | 'bar' | 'doughnut' | 'radar';
  data: any;
  options: any;
  height?: number;
}

const Chartjs: React.FC<ChartjsProps> = ({ type, data, options, height = 220 }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const inst = useRef<Chart | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    applyTheme();

    inst.current = new Chart(ref.current, { type, data, options });

    return () => {
      if (inst.current) {
        inst.current.destroy();
        inst.current = null;
      }
    };
  }, [type, data, options]);

  return (
    <div className="li-chart" style={{ height }}>
      <canvas ref={ref}></canvas>
    </div>
  );
};

// 1. Line Chart
interface LineChartProps {
  labels: string[];
  datasets: Array<{
    label: string;
    data: number[];
    color: string;
  }>;
  height?: number;
  yMax?: number;
}

export const LineChart: React.FC<LineChartProps> = ({ labels, datasets, height = 220, yMax }) => {
  const ds = datasets.map((d) => ({
    label: d.label,
    data: d.data,
    borderColor: resolve(d.color),
    backgroundColor: alpha(d.color, 0.14),
    tension: 0.4,
    fill: true,
    borderWidth: 2.5,
    pointRadius: 3,
    pointHoverRadius: 5,
    pointBackgroundColor: resolve(d.color),
    pointBorderColor: '#fff',
    pointBorderWidth: 1.5,
  }));

  const data = React.useMemo(() => ({ labels, datasets: ds }), [labels, datasets]);

  const options = React.useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: { legend: { display: datasets.length > 1, position: 'top' as const, align: 'end' as const } },
    scales: {
      y: { beginAtZero: true, suggestedMax: yMax, grid: { color: GRID }, border: { display: false }, ticks: { maxTicksLimit: 5 } },
      x: { grid: { display: false }, border: { display: false } },
    },
  }), [datasets.length, yMax]);

  return <Chartjs type="line" height={height} data={data} options={options} />;
};

// 2. Bar Chart
interface BarChartProps {
  labels: string[];
  data: number[];
  colors?: string[];
  height?: number;
  yMax?: number;
  horizontal?: boolean;
}

export const BarChart: React.FC<BarChartProps> = ({
  labels,
  data,
  colors,
  height = 220,
  yMax = 100,
  horizontal = false,
}) => {
  const bg = React.useMemo(() => (colors || []).map((c) => alpha(c, 0.85)), [colors]);
  const datasets = React.useMemo(() => [{
    data,
    backgroundColor: bg.length ? bg : alpha('var(--primary)', 0.85),
    borderRadius: 6,
    borderSkipped: false,
    maxBarThickness: 46,
  }], [data, bg]);

  const chartData = React.useMemo(() => ({ labels, datasets }), [labels, datasets]);

  const options = React.useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: horizontal ? ('y' as const) : ('x' as const),
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (c: any) => ` ${c.raw}` } },
    },
    scales: {
      [horizontal ? 'x' : 'y']: {
        beginAtZero: true,
        max: yMax,
        grid: { color: GRID },
        border: { display: false },
        ticks: { maxTicksLimit: 6 },
      },
      [horizontal ? 'y' : 'x']: {
        grid: { display: false },
        border: { display: false },
      },
    },
  }), [horizontal, yMax]);

  return <Chartjs type="bar" height={height} data={chartData} options={options} />;
};

// 3. Doughnut Chart
interface DoughnutChartProps {
  labels: string[];
  data: number[];
  colors?: string[];
  height?: number;
  legend?: 'top' | 'right' | 'bottom' | 'left';
}

export const DoughnutChart: React.FC<DoughnutChartProps> = ({
  labels,
  data,
  colors,
  height = 220,
  legend = 'right',
}) => {
  const bg = React.useMemo(() => (colors || []).map(resolve), [colors]);
  const datasets = React.useMemo(() => [{
    data,
    backgroundColor: bg,
    borderColor: '#fff',
    borderWidth: 3,
    hoverOffset: 6,
  }], [data, bg]);

  const chartData = React.useMemo(() => ({ labels, datasets }), [labels, datasets]);

  const options = React.useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    cutout: '62%',
    plugins: {
      legend: { position: legend, labels: { font: { size: 12 } } },
      tooltip: { callbacks: { label: (c: any) => ` ${c.label}: %${c.raw}` } },
    },
  }), [legend]);

  return <Chartjs type="doughnut" height={height} data={chartData} options={options} />;
};

// 4. Radar Chart
interface RadarChartProps {
  labels: string[];
  data: number[];
  height?: number;
  color?: string;
}

export const RadarChart: React.FC<RadarChartProps> = ({
  labels,
  data,
  height = 260,
  color = 'var(--primary)',
}) => {
  const datasets = React.useMemo(() => [{
    label: 'Yetkinlik',
    data,
    borderColor: resolve(color),
    backgroundColor: alpha(color, 0.18),
    pointBackgroundColor: resolve(color),
    pointBorderColor: '#fff',
    borderWidth: 2,
    pointRadius: 3,
  }], [data, color]);

  const chartData = React.useMemo(() => ({ labels, datasets }), [labels, datasets]);

  const options = React.useMemo(() => {
    const css = rootCss();
    const primaryColor = css ? css.getPropertyValue('--text-primary').trim() : '#222';
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c: any) => ` %${c.raw}` } },
      },
      scales: {
        r: {
          suggestedMin: 0,
          suggestedMax: 100,
          ticks: { stepSize: 20, backdropColor: 'transparent', font: { size: 10 } },
          grid: { color: GRID },
          angleLines: { color: GRID },
          pointLabels: {
            font: { size: 12, weight: '600' as const },
            color: primaryColor || '#222',
          },
        },
      },
    };
  }, []);

  return <Chartjs type="radar" height={height} data={chartData} options={options} />;
};

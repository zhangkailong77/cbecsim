import { useEffect, useMemo, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type MetricKey = 'sales_amount' | 'buyers_count' | 'orders_count' | 'units_sold' | 'items_sold';
type TimeBasis = 'order_time' | 'completed_time';

interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

interface MetricCards {
  sales_amount: number;
  units_sold: number;
  orders_count: number;
  buyers_count: number;
  items_sold: number;
}

interface TrendPoint extends MetricCards {
  stat_date: string;
}

interface RankingRow {
  rank: number;
  campaign_item_id: number;
  product_id: number | null;
  product_name: string;
  image_url: string | null;
  variation_name: string | null;
  original_price: number;
  discount_label: string;
  discounted_price: number | null;
  units_sold: number;
  buyers_count: number;
  sales_amount: number;
}

interface RankingList {
  rows: RankingRow[];
  pagination: PaginationMeta;
}

interface AvailableYear {
  year: number;
  label: string;
}

interface DiscountDataResponse {
  campaign_id: number;
  campaign_name: string;
  campaign_type_label: string;
  status: string;
  status_label: string;
  start_at: string | null;
  end_at: string | null;
  market: string;
  currency: string;
  time_basis: TimeBasis;
  data_period_text?: string;
  available_years: AvailableYear[];
  selected_game_year: number;
  metric_cards: MetricCards;
  trend: { rows: TrendPoint[]; monthly_rows: TrendPoint[] };
  product_ranking: RankingList;
  export_enabled: boolean;
}

interface DiscountDataViewProps {
  runId: number | null;
  campaignId: number | null;
  publicId: string;
  readOnly?: boolean;
  onBackToDiscount: () => void;
}

const metricOptions: Array<{ key: MetricKey; label: string; title: string; color: string }> = [
  { key: 'sales_amount', label: '销售额', title: '销售额', color: '#2f80ed' },
  { key: 'units_sold', label: '售出件数', title: '售出件数', color: '#f2994a' },
  { key: 'orders_count', label: '订单', title: '订单数', color: '#eb5757' },
  { key: 'buyers_count', label: '买家', title: '买家数', color: '#2dccd3' },
  { key: 'items_sold', label: '售出商品数', title: '售出商品数', color: '#8e44ad' },
];

function formatMoney(value: number | null | undefined) {
  return `RM ${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatMetricValue(key: MetricKey, value: number) {
  if (key === 'sales_amount') return formatMoney(value);
  return Number(value || 0).toLocaleString('en-US');
}

function formatTrendDate(value: string) {
  const [year, month, day] = value.replaceAll('/', '-').split('-');
  return year && month && day ? `${day}-${month}-${year}` : value;
}

function buildPaginationItems(currentPage: number, totalPages: number): Array<number | 'ellipsis'> {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 4) return [1, 2, 3, 4, 5, 'ellipsis', totalPages];
  if (currentPage >= totalPages - 3) return [1, 'ellipsis', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  return [1, 'ellipsis', currentPage - 1, currentPage, currentPage + 1, 'ellipsis', totalPages];
}

function Pagination({ meta, onPageChange }: { meta: PaginationMeta; onPageChange: (page: number) => void }) {
  const currentPage = meta.page || 1;
  const totalPages = Math.max(1, meta.total_pages || 1);
  const pages = buildPaginationItems(currentPage, totalPages);
  return (
    <div className="flex items-center justify-end gap-2 px-4 py-4 text-[12px] text-[#666]">
      <button type="button" disabled={currentPage <= 1} onClick={() => onPageChange(currentPage - 1)} className="h-8 min-w-8 border border-[#d8d8d8] bg-white px-2 disabled:cursor-not-allowed disabled:opacity-40">{'<'}</button>
      {pages.map((item, index) => item === 'ellipsis' ? (
        <span key={`ellipsis-${index}`} className="px-1 text-[#999]">...</span>
      ) : (
        <button key={item} type="button" onClick={() => onPageChange(item)} className={`h-8 min-w-8 border px-2 ${item === currentPage ? 'border-[#ee4d2d] bg-[#ee4d2d] text-white' : 'border-[#d8d8d8] bg-white text-[#666] hover:border-[#ee4d2d] hover:text-[#ee4d2d]'}`}>{item}</button>
      ))}
      <button type="button" disabled={currentPage >= totalPages} onClick={() => onPageChange(currentPage + 1)} className="h-8 min-w-8 border border-[#d8d8d8] bg-white px-2 disabled:cursor-not-allowed disabled:opacity-40">{'>'}</button>
    </div>
  );
}

function TrendChart({
  rows,
  monthlyRows,
  selectedMetrics,
  selectedGameYear,
}: {
  rows: TrendPoint[];
  monthlyRows: TrendPoint[];
  selectedMetrics: MetricKey[];
  selectedGameYear: number;
}) {
  const selectedOptions = metricOptions.filter((metric) => selectedMetrics.includes(metric.key));
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const width = 980;
  const height = 230;
  const paddingX = 48;
  const paddingY = 24;
  const chartWidth = width - paddingX * 2;
  const chartHeight = height - paddingY * 2;

  let displayRows: Array<TrendPoint & { display_label: string }> = [];

  if (selectedGameYear > 0) {
    for (let month = 1; month <= 12; month++) {
      const mm = String(month).padStart(2, '0');
      const targetMonthPrefix = `${selectedGameYear}-${mm}`;
      const foundData = monthlyRows.find((row) => row.stat_date.replaceAll('/', '-').startsWith(targetMonthPrefix));

      displayRows.push({
        stat_date: `${targetMonthPrefix}-01`,
        sales_amount: 0,
        units_sold: 0,
        orders_count: 0,
        buyers_count: 0,
        items_sold: 0,
        ...foundData,
        display_label: `${mm}-${selectedGameYear}`,
      });
    }
  } else {
    displayRows = rows.map((row) => {
      const parts = row.stat_date.replaceAll('/', '-').split('-');
      const label = parts.length >= 3 ? `${parts[2]}-${parts[1]}` : row.stat_date;
      return { ...row, display_label: label };
    });
  }

  // 防止重叠的高度系数
  const ceilingMultipliers: Record<MetricKey, number> = {
    sales_amount: 1.1,
    units_sold: 1.35,
    orders_count: 1.6,
    buyers_count: 1.85,
    items_sold: 2.1,
  };

  const metricPoints = selectedOptions.map((metric) => {
    const points = displayRows.map((row) => Number(row[metric.key] || 0));
    const actualMax = Math.max(1, ...points);
    return {
      ...metric,
      points,
      chartMaxValue: actualMax * ceilingMultipliers[metric.key as MetricKey],
    };
  });

  const getXByIndex = (index: number) =>
    paddingX + (displayRows.length <= 1 ? chartWidth / 2 : (index / (displayRows.length - 1)) * chartWidth);

  if (!displayRows || !displayRows.length || selectedOptions.length === 0) {
    return <div className="flex h-[260px] items-center justify-center text-[13px] text-[#999]">该活动暂无订单数据</div>;
  }

  const animationKey = displayRows.length > 0 ? `${displayRows[0].stat_date}-${displayRows.length}-${selectedMetrics.join('-')}` : 'empty';

  return (
    <div className="relative">
      <div className="mb-2 flex justify-end gap-4 text-[11px] text-[#666]">
        {selectedOptions.map((metric) => (
          <span key={metric.key} className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: metric.color }} />
            {metric.title}
          </span>
        ))}
        <span className="inline-flex items-center border border-[#d8d8d8] px-2 py-0.5 text-[#666]">
          Metrics Selected {selectedOptions.length} / 4
        </span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="h-[260px] w-full" onMouseLeave={() => setHoverIndex(null)}>
        <style>
          {`
            @keyframes wipeRight {
              from { clip-path: inset(0 100% 0 0); }
              to { clip-path: inset(0 0 0 0); }
            }
            .animate-chart-wipe {
              animation: wipeRight 1.2s ease-in-out forwards;
            }
          `}
        </style>

        {[0, 1, 2, 3].map((line) => {
          const y = paddingY + (line / 3) * chartHeight;
          return <line key={`grid-${line}`} x1={paddingX} x2={width - paddingX} y1={y} y2={y} stroke="#eeeeee" strokeWidth="1" />;
        })}

        {/* 底部文案 */}
        {displayRows.map((row, index) => {
          // 如果点数超过 12 个（日常模式），防止文字挤压，跳着显示。如果是 12 个月内，则全部显示。
          if (displayRows.length > 12 && index % Math.ceil(displayRows.length / 8) !== 0 && index !== displayRows.length - 1) return null;
          const x = getXByIndex(index);
          return (
            <text key={`label-${index}`} x={x} y={height - 5} textAnchor="middle" className="fill-[#999] text-[11px]">
              {row.display_label}
            </text>
          );
        })}

        {metricPoints.map((metric) => {
          const path = metric.points
            .map((value, index) => {
              const x = getXByIndex(index);
              const y = paddingY + chartHeight - (value / metric.chartMaxValue) * chartHeight;
              return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
            })
            .join(' ');

          return (
            <g key={`${metric.key}-${animationKey}`} className="animate-chart-wipe pointer-events-none">
              <path d={path} fill="none" stroke={metric.color} strokeWidth="2" />
              {displayRows.map((row, index) => {
                const value = metric.points[index] || 0;
                const x = getXByIndex(index);
                const y = paddingY + chartHeight - (value / metric.chartMaxValue) * chartHeight;
                return <circle key={`circle-${metric.key}-${index}`} cx={x} cy={y} r="2.8" fill={metric.color} />;
              })}
            </g>
          );
        })}

        {hoverIndex !== null && (
          <g className="pointer-events-none">
            <line
              x1={getXByIndex(hoverIndex)}
              x2={getXByIndex(hoverIndex)}
              y1={paddingY}
              y2={height - paddingY}
              stroke="#d1d5db"
              strokeWidth="1"
              strokeDasharray="4 4"
            />
            {metricPoints.map((metric) => {
              const value = metric.points[hoverIndex] || 0;
              const x = getXByIndex(hoverIndex);
              const y = paddingY + chartHeight - (value / metric.chartMaxValue) * chartHeight;
              return <circle key={`hl-${metric.key}`} cx={x} cy={y} r="4.5" fill={metric.color} stroke="#ffffff" strokeWidth="2" />;
            })}
          </g>
        )}

        {/* 鼠标感应区 */}
        <g>
          {displayRows.map((_, index) => {
            const x = getXByIndex(index);
            const sectionWidth = displayRows.length > 1 ? chartWidth / (displayRows.length - 1) : chartWidth;
            return (
              <rect
                key={`target-${index}`}
                x={x - sectionWidth / 2}
                y={paddingY}
                width={sectionWidth}
                height={chartHeight}
                fill="transparent"
                className="cursor-crosshair"
                onMouseEnter={() => setHoverIndex(index)}
              />
            );
          })}
        </g>
      </svg>

      {hoverIndex !== null && (
        <div
          className="pointer-events-none absolute top-4 z-10 rounded bg-white px-3 py-2.5 text-[12px] shadow-[0_4px_12px_rgba(0,0,0,0.1)] ring-1 ring-black/5 transition-all duration-100 ease-out"
          style={{
            left: `${(getXByIndex(hoverIndex) / width) * 100}%`,
            transform: getXByIndex(hoverIndex) > width / 2 ? 'translateX(calc(-100% - 16px))' : 'translateX(16px)',
          }}
        >
          {/* Tooltip 标题 */}
          <div className="mb-2.5 font-medium text-gray-800">
             {monthlyRows?.length > 0 ? displayRows[hoverIndex].display_label : formatTrendDate(displayRows[hoverIndex].stat_date)}
          </div>
          <div className="flex flex-col gap-1.5">
            {selectedOptions.map((metric) => {
              const rawValue = Number(displayRows[hoverIndex][metric.key] || 0);
              return (
                <div key={metric.key} className="flex items-center justify-between gap-6">
                  <span className="flex items-center gap-1.5 text-gray-500">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: metric.color }} />
                    {metric.title}
                  </span>
                  <span className="font-semibold text-gray-900">{formatMetricValue(metric.key, rawValue)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DiscountDataView({ runId, campaignId, publicId, readOnly = false, onBackToDiscount }: DiscountDataViewProps) {
  const [data, setData] = useState<DiscountDataResponse | null>(null);
  const [ranking, setRanking] = useState<RankingList | null>(null);
  const [selectedMetrics, setSelectedMetrics] = useState<MetricKey[]>(['sales_amount', 'units_sold', 'orders_count', 'buyers_count']);
  const [timeBasis, setTimeBasis] = useState<TimeBasis>('order_time');
  const [loading, setLoading] = useState(false);
  const [rankingLoading, setRankingLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showTrendDetails, setShowTrendDetails] = useState(false);
  const [gameYear, setGameYear] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!runId || !campaignId) {
      setError('缺少活动信息，无法加载数据页。');
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    let cancelled = false;
    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        const params = new URLSearchParams({ time_basis: timeBasis });
        if (gameYear > 0) params.set('game_year', String(gameYear));
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/discount/campaigns/${campaignId}/data?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('data failed');
        const result = (await response.json()) as DiscountDataResponse;
        if (cancelled) return;
        setData(result);
        setRanking(result.product_ranking);
        if (gameYear === 0 && result.selected_game_year) {
          setGameYear(result.selected_game_year);
        }
      } catch {
        if (!cancelled) setError('折扣数据加载失败，请稍后重试。');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void loadData();
    return () => {
      cancelled = true;
    };
  }, [campaignId, runId, timeBasis, gameYear]);

  const periodText = useMemo(() => `${data?.start_at || '-'} - ${data?.end_at || '-'}`, [data]);

  const loadRanking = async (page: number) => {
    if (!runId || !campaignId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    setRankingLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '10', sort: 'sales_amount', order: 'desc', time_basis: timeBasis });
      if (gameYear > 0) params.set('game_year', String(gameYear));
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/discount/campaigns/${campaignId}/data/ranking?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('ranking failed');
      setRanking((await response.json()) as RankingList);
    } catch {
      setError('商品排行加载失败，请稍后重试。');
    } finally {
      setRankingLoading(false);
    }
  };

  const toggleMetric = (metricKey: MetricKey) => {
    setSelectedMetrics((prev) => {
      if (prev.includes(metricKey)) {
        return prev.length <= 1 ? prev : prev.filter((key) => key !== metricKey);
      }
      if (prev.length >= 4) return prev;
      return [...prev, metricKey];
    });
  };

  const handleOpenDetail = () => {
    if (!publicId || !campaignId) return;
    window.history.pushState(null, '', `/u/${encodeURIComponent(publicId)}/shopee/marketing/discount/detail?campaign_id=${campaignId}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const handleExport = async () => {
    if (!runId || !campaignId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    setExporting(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/discount/campaigns/${campaignId}/data/export`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ time_basis: timeBasis, export_type: 'csv' }),
      });
      if (!response.ok) throw new Error('export failed');
      const result = (await response.json()) as { download_url?: string | null };
      if (result.download_url) {
        const link = document.createElement('a');
        link.href = result.download_url;
        link.download = `discount-data-${campaignId}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
      }
    } catch {
      setError('导出失败，请稍后重试。');
    } finally {
      setExporting(false);
    }
  };

  const trendRows = data?.trend.rows ?? [];
  const monthlyTrendRows = data?.trend.monthly_rows ?? [];
  const metricCards = data?.metric_cards;

  return (
    <div className="flex-1 overflow-y-auto bg-[#f5f5f5] px-10 py-6 custom-scrollbar">
      <div className="mx-auto max-w-[1360px] pb-10">
        {error ? <div className="mb-4 border border-[#ffd6cc] bg-[#fff7f5] px-4 py-3 text-[13px] text-[#d63b1f]">{error}</div> : null}

        {/* <div className="mb-3 flex h-9 w-[220px] items-center justify-between border border-[#d8d8d8] bg-white px-3 text-[12px] text-[#333]">
          <span>马来西亚站点 · {data?.market || 'MY'}</span>
          <span className="text-[#999]">⌄</span>
        </div> */}

        <section className="mb-4 bg-white px-4 py-4">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-[18px] font-semibold text-gray-900">{loading ? '加载中...' : data?.campaign_name || '折扣数据'}</h1>
                {data ? <span className="rounded-[2px] bg-[#f4f4f4] px-2 py-1 text-[12px] text-[#777]">{data.status_label}</span> : null}
                <button type="button" onClick={handleOpenDetail} className="text-[12px] font-medium text-[#2673dd] hover:underline">Promotion Details &gt;</button>
                {readOnly ? <span className="border border-amber-200 bg-amber-50 px-2 py-1 text-[12px] text-amber-700">历史回溯只读</span> : null}
              </div>
              <div className="mt-2 text-[12px] text-gray-500">活动时间：{periodText}</div>
            </div>
            <div className="flex items-center gap-2">
              <select value={timeBasis} onChange={(event) => setTimeBasis(event.target.value as TimeBasis)} className="h-8 border border-[#d8d8d8] bg-white px-3 text-[12px] text-[#333] outline-none">
                <option value="order_time">订单时间</option>
                <option value="completed_time">已完成订单</option>
              </select>
              <button type="button" onClick={handleExport} disabled={exporting || !data?.export_enabled} className="h-8 border border-[#d8d8d8] bg-white px-4 text-[12px] text-[#333] hover:border-[#ee4d2d] hover:text-[#ee4d2d] disabled:cursor-not-allowed disabled:opacity-50">
                {exporting ? '导出中...' : '导出数据'}
              </button>
            </div>
          </div>
        </section>

        <section className="bg-white">
          {data?.data_period_text ? (
            <div className="flex items-center gap-3 px-4 pt-4">
              <div className="text-[13px] text-[#555]">
                关键指标（数据周期：{data.data_period_text}）
              </div>
              {data.available_years.length > 1 ? (
                <select
                  value={gameYear}
                  onChange={(e) => setGameYear(Number(e.target.value))}
                  className="h-7 border border-[#d8d8d8] bg-white px-2 text-[12px] text-[#333] outline-none"
                >
                  {data.available_years.map((item) => (
                    <option key={item.year} value={item.year}>{item.label}</option>
                  ))}
                </select>
              ) : null}
            </div>
          ) : null}
          <div className="grid grid-cols-5 gap-3 px-4 py-4">
            {metricOptions.map((metric) => {
              const selected = selectedMetrics.includes(metric.key);
              const disabled = !selected && selectedMetrics.length >= 4;
              return (
                <button
                  key={metric.key}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggleMetric(metric.key)}
                  className={`relative border bg-white p-3 text-left disabled:cursor-not-allowed disabled:opacity-45 ${selected ? 'border-[#d8d8d8]' : 'border-[#e5e5e5]'}`}
                >
                  {selected ? <span className="absolute left-0 top-0 h-[3px] w-full" style={{ backgroundColor: metric.color }} /> : null}
                  <div className="text-[12px] text-gray-500">
                    <span>{metric.title}</span>
                  </div>
                  <div className="mt-2 text-[18px] font-semibold text-gray-900">{formatMetricValue(metric.key, Number(metricCards?.[metric.key] || 0))}</div>
                </button>
              );
            })}
          </div>

          <div className="border-t border-[#eeeeee] px-4 py-4">
            <div className="mb-2 text-[13px] font-medium text-gray-700">Trend Chart of Each Metric</div>
            <TrendChart
              rows={trendRows}
              monthlyRows={monthlyTrendRows}
              selectedMetrics={selectedMetrics}
              selectedGameYear={data?.selected_game_year ?? gameYear}
            />
            {trendRows.length > 0 ? (
              <div className="mt-3">
                <div className="flex justify-center">
                  <button type="button" onClick={() => setShowTrendDetails((value) => !value)} className="h-7 bg-transparent px-2 text-[12px] font-medium text-[#2673dd] hover:underline">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      {showTrendDetails ? 'Hide Details' : 'Check Details'}
                      <svg 
                        width="16" 
                        height="16" 
                        viewBox="0 0 24 24" 
                        fill="none" 
                        stroke="currentColor" 
                        strokeWidth="2" 
                        strokeLinecap="round" 
                        strokeLinejoin="round"
                        style={{ 
                          transform: showTrendDetails ? 'rotate(180deg)' : 'rotate(0deg)',
                          transition: 'transform 0.2s ease-in-out' // 加了 ease-in-out 让动画更柔和一点
                        }}
                      >
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </span>
                  </button>
                </div>
                {showTrendDetails ? (
                  <div className="mt-3 overflow-hidden border border-[#eeeeee]">
                    <div className="grid grid-cols-6 bg-[#f7f7f7] px-4 py-3 text-[12px] font-medium text-gray-500">
                      <div>Date</div>
                      <div>Sales</div>
                      <div>Units Sold</div>
                      <div>Orders</div>
                      <div>Buyers</div>
                      <div>Sales Per Buyer</div>
                    </div>
                    {trendRows.map((row) => {
                      const buyers = Number(row.buyers_count || 0);
                      const sales = Number(row.sales_amount || 0);
                      const salesPerBuyer = buyers > 0 ? sales / buyers : 0;
                      return (
                        <div key={row.stat_date} className="grid grid-cols-6 border-t border-[#eeeeee] px-4 py-3 text-[12px] text-gray-700">
                          <div>{formatTrendDate(row.stat_date)}</div>
                          <div>{formatMoney(sales)}</div>
                          <div>{Number(row.units_sold || 0).toLocaleString('en-US')}</div>
                          <div>{Number(row.orders_count || 0).toLocaleString('en-US')}</div>
                          <div>{buyers.toLocaleString('en-US')}</div>
                          <div>{formatMoney(salesPerBuyer)}</div>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </section>

        <section className="mt-4 bg-white">
          <div className="flex items-center justify-between border-b border-[#eeeeee] px-4 py-3">
            <h2 className="text-[13px] font-medium text-gray-700">Product Ranking</h2>
            {rankingLoading ? <span className="text-[12px] text-[#999]">加载中...</span> : null}
          </div>
          <div className="grid grid-cols-[72px_minmax(320px,1.6fr)_130px_130px_120px_120px_120px_130px] bg-[#f7f7f7] px-4 py-3 text-[12px] font-medium text-gray-500">
            <div>Ranking</div>
            <div>Product</div>
            <div>Variation</div>
            <div>Original Price</div>
            <div>Discount</div>
            <div>Units Sold</div>
            <div>Buyers</div>
            <div>Sales</div>
          </div>
          {(ranking?.rows ?? []).length > 0 ? ranking?.rows.map((row) => (
            <div key={row.campaign_item_id} className="grid grid-cols-[72px_minmax(320px,1.6fr)_130px_130px_120px_120px_120px_130px] border-t border-[#eeeeee] px-4 py-2.5 text-[12px] text-gray-700">
              <div className="pt-3">{row.rank}</div>
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center border border-[#e1e1e1] bg-[#fafafa] text-[11px] text-[#999]" style={row.image_url ? { backgroundImage: `url(${row.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}>{!row.image_url ? '图片' : ''}</div>
                <div className="min-w-0">
                  <div className="line-clamp-2 text-[12px] font-medium text-gray-800">{row.product_name}</div>
                  <div className="mt-1 truncate text-[11px] text-gray-500">商品 ID：{row.product_id || '-'}</div>
                </div>
              </div>
              <div className="pt-3 text-[11px] text-gray-500">{row.variation_name || '-'}</div>
              <div className="pt-3">{formatMoney(row.original_price)}</div>
              <div className="pt-2"><span className="inline-flex h-5 items-center border border-[#ee4d2d] px-1.5 text-[11px] text-[#ee4d2d]">{row.discount_label}</span></div>
              <div className="pt-3">{row.units_sold}</div>
              <div className="pt-3">{row.buyers_count}</div>
              <div className="pt-3">{formatMoney(row.sales_amount)}</div>
            </div>
          )) : <div className="border-t border-[#eeeeee] px-4 py-16 text-center text-[13px] text-[#999]">该活动暂无订单数据</div>}
          {ranking ? <Pagination meta={ranking.pagination} onPageChange={(page) => loadRanking(page)} /> : null}
        </section>

        <div className="mt-6 flex justify-end">
          <button type="button" onClick={onBackToDiscount} className="h-10 min-w-[132px] border border-[#d9d9d9] bg-white px-6 text-[14px] font-medium text-[#555] hover:border-[#ee4d2d] hover:text-[#ee4d2d]">返回列表页</button>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';
import { HelpCircle, RefreshCw, Package, ChevronDown, ChevronUp } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type TabType = 'all' | 'unpaid' | 'toship' | 'shipping' | 'completed';
type OrderType = 'all' | 'order' | 'command' | 'advance';
type OrderStatus = 'all' | 'processing' | 'processed';
type Priority = 'all' | 'overdue' | 'today' | 'tomorrow';

interface OrderItem {
  product_name: string;
  variant_name: string;
  quantity: number;
  unit_price: number;
  image_url: string | null;
}

interface OrderRow {
  id: number;
  order_no: string;
  buyer_name: string;
  buyer_payment: number;
  order_type: OrderType;
  type_bucket: TabType;
  process_status: OrderStatus;
  shipping_priority: string;
  shipping_channel: string;
  destination: string;
  countdown_text: string;
  action_text: string;
  created_at: string;
  items: OrderItem[];
}

interface OrdersResponse {
  counts: {
    all: number;
    unpaid: number;
    toship: number;
    shipping: number;
    completed: number;
  };
  page: number;
  page_size: number;
  total: number;
  simulated_recent_1h: number;
  last_simulated_at: string | null;
  orders: OrderRow[];
}

interface MyOrdersViewProps {
  runId: number | null;
}

function queryFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const tabType = (params.get('type') ?? 'all') as TabType;
  return {
    type: ['all', 'unpaid', 'toship', 'shipping', 'completed'].includes(tabType) ? tabType : 'all',
    source: params.get('source') ?? '',
    sortBy: params.get('sort_by') ?? '',
    orderType: (params.get('order_type') ?? 'all') as OrderType,
    orderStatus: (params.get('order_status') ?? 'all') as OrderStatus,
    priority: (params.get('priority') ?? 'all') as Priority,
    keyword: params.get('keyword') ?? '',
    channel: params.get('channel') ?? '',
  };
}

function buildBaseParamsByType(type: TabType) {
  const params = new URLSearchParams();
  if (type === 'unpaid') params.set('type', 'unpaid');
  if (type === 'shipping') params.set('type', 'shipping');
  if (type === 'completed') params.set('type', 'completed');
  if (type === 'toship') {
    params.set('type', 'toship');
    params.set('source', 'to_process');
    params.set('sort_by', 'ship_by_date_asc');
  }
  return params;
}

function FilterChip({
  label,
  active = false,
  onClick,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`h-9 rounded-full border px-4 text-[14px] transition-colors ${
        active
          ? 'border-[#ee4d2d] text-[#ee4d2d] bg-white'
          : 'border-gray-200 text-gray-600 bg-white hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  );
}

function formatMoney(amount: number) {
  return `RM${Math.max(0, Number(amount || 0))}`;
}

function buildOrderActions(actionText?: string) {
  return [
    '查看物流详情',
    actionText?.trim() || '查看详情',
    '打印面单',
  ];
}

export default function MyOrdersView({ runId }: MyOrdersViewProps) {
  const [query, setQuery] = useState(queryFromLocation());
  const [data, setData] = useState<OrdersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchField, setSearchField] = useState('订单号');
  const [searchDropdownOpen, setSearchDropdownOpen] = useState(false);
  const searchDropdownRef = useRef<HTMLDivElement | null>(null);

  const updateUrl = (params: URLSearchParams) => {
    const next = params.toString();
    const nextUrl = next ? `${window.location.pathname}?${next}` : window.location.pathname;
    window.history.pushState(null, '', nextUrl);
    setQuery(queryFromLocation());
  };

  const applyQueryPatch = (patch: Partial<typeof query>) => {
    const base = buildBaseParamsByType(query.type);
    const next = { ...query, ...patch };

    if (next.type === 'toship') {
      if (next.orderType !== 'all') base.set('order_type', next.orderType);
      if (next.orderStatus !== 'all') base.set('order_status', next.orderStatus);
      if (next.priority !== 'all') base.set('priority', next.priority);
    }
    if (next.keyword.trim()) base.set('keyword', next.keyword.trim());
    if (next.channel.trim()) base.set('channel', next.channel.trim());
    updateUrl(base);
  };

  const switchTab = (type: TabType) => {
    updateUrl(buildBaseParamsByType(type));
  };

  useEffect(() => {
    const onPop = () => setQuery(queryFromLocation());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  useEffect(() => {
    const onDocClick = (event: MouseEvent) => {
      if (!searchDropdownRef.current) return;
      if (!searchDropdownRef.current.contains(event.target as Node)) {
        setSearchDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    const params = new URLSearchParams(window.location.search);
    params.set('page', '1');
    params.set('page_size', '20');

    setLoading(true);
    fetch(`${API_BASE_URL}/shopee/runs/${runId}/orders?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error('load failed');
        return res.json();
      })
      .then((res: OrdersResponse) => setData(res))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [runId, query]);

  const countText = useMemo(() => {
    if (!data) return '0';
    return String(data.total ?? 0);
  }, [data]);

  const shippingChannelOptions = useMemo(() => {
    const set = new Set<string>();
    (data?.orders ?? []).forEach((row) => set.add(row.shipping_channel));
    return ['所有频道', ...Array.from(set)];
  }, [data]);

  const keywordPlaceholderMap: Record<string, string> = {
    订单号: '输入订单/预订编号',
    买方名称: '输入买方名称',
    产品: '输入产品关键词',
    追踪号码: '输入追踪号码',
    '返回请求 ID': '输入返回请求 ID',
    退货追踪号: '输入退货追踪号',
  };

  const searchFieldOptions = ['订单号', '买方名称', '产品', '追踪号码', '返回请求 ID', '退货追踪号'];

  return (
    <div className="flex-1 bg-[#f5f5f5] p-6 overflow-y-auto custom-scrollbar">
      <div className="max-w-[1600px] mx-auto">
        <div className="bg-white border border-gray-100 rounded-sm p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-[16px] leading-none font-semibold text-gray-800">我的订单</h2>
            <div className="flex items-center gap-3">
              <button type="button" className="h-9 px-5 rounded border border-gray-300 text-[14px] text-gray-700 hover:bg-gray-50">
                出口
              </button>
              <button type="button" className="h-9 px-5 rounded border border-gray-300 text-[14px] text-gray-700 hover:bg-gray-50 relative">
                出口历史
                <span className="absolute -top-2 -right-2 min-w-5 h-5 px-1 rounded-full bg-[#ee4d2d] text-white text-[11px] leading-5 text-center">7</span>
              </button>
            </div>
          </div>

          <div className="mt-7 border-b border-gray-200 flex items-center gap-8">
            <button
              type="button"
              onClick={() => switchTab('all')}
              className={`pb-3 text-[14px] ${query.type === 'all' ? 'text-[#ee4d2d] border-b-2 border-[#ee4d2d]' : 'text-gray-600'}`}
            >
              全部
            </button>
            <button
              type="button"
              onClick={() => switchTab('unpaid')}
              className={`pb-3 text-[14px] ${query.type === 'unpaid' ? 'text-[#ee4d2d] border-b-2 border-[#ee4d2d]' : 'text-gray-600'}`}
            >
              待付款（{data?.counts.unpaid ?? 0}）
            </button>
            <button
              type="button"
              onClick={() => switchTab('toship')}
              className={`pb-3 text-[14px] ${query.type === 'toship' ? 'text-[#ee4d2d] border-b-2 border-[#ee4d2d]' : 'text-gray-600'}`}
            >
              待出货（{data?.counts.toship ?? 0}）
            </button>
            <button
              type="button"
              onClick={() => switchTab('shipping')}
              className={`pb-3 text-[14px] ${query.type === 'shipping' ? 'text-[#ee4d2d] border-b-2 border-[#ee4d2d]' : 'text-gray-600'}`}
            >
              运输中（{data?.counts.shipping ?? 0}）
            </button>
            <button
              type="button"
              onClick={() => switchTab('completed')}
              className={`pb-3 text-[14px] ${query.type === 'completed' ? 'text-[#ee4d2d] border-b-2 border-[#ee4d2d]' : 'text-gray-600'}`}
            >
              已完成（{data?.counts.completed ?? 0}）
            </button>
          </div>

          {(data?.simulated_recent_1h ?? 0) > 0 && (
            <div className="mt-4 rounded border border-[#fcd9d1] bg-[#fff6f4] px-4 py-2 text-[13px] text-[#c2410c]">
              最近1小时新增 <span className="font-bold">{data?.simulated_recent_1h ?? 0}</span> 单（买家池系统模拟）
              {data?.last_simulated_at ? `，最近一次：${new Date(data.last_simulated_at).toLocaleString()}` : ''}
            </div>
          )}

          {(query.type === 'all' || query.type === 'shipping') && (
            <div className="mt-8">
              <div className="flex items-center gap-4">
                <div className="w-[94px] text-[14px] text-gray-500">订单类型</div>
                <div className="flex items-center gap-2">
                  <FilterChip
                    label={`订单（${data?.total ?? 0}）`}
                    active={query.orderType === 'order' || query.orderType === 'all'}
                    onClick={() => applyQueryPatch({ orderType: 'order' })}
                  />
                  <FilterChip
                    label="提前履行(0)"
                    active={query.orderType === 'advance'}
                    onClick={() => applyQueryPatch({ orderType: 'advance' })}
                  />
                </div>
              </div>
            </div>
          )}

          {query.type === 'toship' && (
            <div className="mt-8 space-y-4">
              <div className="flex items-center gap-4">
                <div className="w-[94px] text-[14px] text-gray-500">订单类型</div>
                <div className="flex items-center gap-2">
                  <FilterChip label="全部" active={query.orderType === 'all'} onClick={() => applyQueryPatch({ orderType: 'all' })} />
                  <FilterChip label="命令" active={query.orderType === 'command'} onClick={() => applyQueryPatch({ orderType: 'command' })} />
                  <FilterChip label="提前履行" active={query.orderType === 'advance'} onClick={() => applyQueryPatch({ orderType: 'advance' })} />
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="w-[94px] text-[14px] text-gray-500">订单状态</div>
                <div className="flex items-center gap-2">
                  <FilterChip label="全部" active={query.orderStatus === 'all'} onClick={() => applyQueryPatch({ orderStatus: 'all' })} />
                  <FilterChip label="处理" active={query.orderStatus === 'processing'} onClick={() => applyQueryPatch({ orderStatus: 'processing' })} />
                  <FilterChip label="已处理" active={query.orderStatus === 'processed'} onClick={() => applyQueryPatch({ orderStatus: 'processed' })} />
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="w-[94px] text-[14px] text-gray-500">优先发货</div>
                <div className="flex items-center gap-2">
                  <FilterChip label="全部" active={query.priority === 'all'} onClick={() => applyQueryPatch({ priority: 'all' })} />
                  <FilterChip label="逾期" active={query.priority === 'overdue'} onClick={() => applyQueryPatch({ priority: 'overdue' })} />
                  <FilterChip label="当日发货" active={query.priority === 'today'} onClick={() => applyQueryPatch({ priority: 'today' })} />
                  <FilterChip label="明日发货" active={query.priority === 'tomorrow'} onClick={() => applyQueryPatch({ priority: 'tomorrow' })} />
                </div>
              </div>
            </div>
          )}

          <div className="mt-5 flex items-center gap-3">
            <div ref={searchDropdownRef} className="relative h-10 w-[240px]">
              <button
                type="button"
                onClick={() => setSearchDropdownOpen((prev) => !prev)}
                className={`flex h-full w-full items-center justify-between border px-4 text-[14px] text-gray-700 bg-white ${
                  searchDropdownOpen ? 'border-[#ee4d2d]' : 'border-gray-300'
                } rounded`}
              >
                <span>{searchField}</span>
                {searchDropdownOpen ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
              </button>
              {searchDropdownOpen && (
                <div className="absolute left-0 top-[42px] z-20 w-full overflow-hidden rounded border border-gray-200 bg-white shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
                  {searchFieldOptions.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => {
                        setSearchField(option);
                        setSearchDropdownOpen(false);
                      }}
                      className={`block h-10 w-full px-4 text-left text-[14px] ${
                        option === searchField ? 'text-[#ee4d2d] bg-[#fff7f5]' : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <input
              value={query.keyword}
              onChange={(e) => setQuery((prev) => ({ ...prev, keyword: e.target.value }))}
              className="h-10 flex-1 border border-gray-300 rounded px-4 text-[14px] text-gray-700"
              placeholder={keywordPlaceholderMap[searchField] ?? '输入关键词'}
            />
            <select
              value={query.channel || '所有频道'}
              onChange={(e) => {
                const value = e.target.value === '所有频道' ? '' : e.target.value;
                setQuery((prev) => ({ ...prev, channel: value }));
              }}
              className="h-10 w-[420px] border border-gray-300 rounded px-4 text-[14px] text-gray-700"
            >
              {shippingChannelOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => applyQueryPatch({ keyword: query.keyword, channel: query.channel })}
              className="h-10 px-7 rounded border border-[#ee4d2d] text-[#ee4d2d] text-[14px] hover:bg-[#fff7f5]"
            >
              申请
            </button>
            <button
              type="button"
              onClick={() => updateUrl(buildBaseParamsByType(query.type))}
              className="h-10 px-7 rounded border border-gray-300 text-gray-700 text-[14px] hover:bg-gray-50"
            >
              重设
            </button>
          </div>

          <div className="mt-6 flex items-center justify-end text-[14px] text-[#3478f6] gap-2">
            <RefreshCw size={14} />
            发货后快速付款
          </div>

          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-1 text-[16px] font-semibold text-gray-800">
              <span>{countText} 单</span>
              <HelpCircle size={16} className="text-gray-400 mt-0.5" />
            </div>
            <div className="flex items-center gap-6">
              <div className="text-[14px] text-gray-600">排序方式： 按发货日期排序（最早的在前）</div>
              <button type="button" className="h-10 px-5 rounded bg-[#ee4d2d] text-white text-[14px] hover:bg-[#d73211] flex items-center gap-2">
                <Package size={14} />
                批量发货
              </button>
            </div>
          </div>

          <div className="mt-3 border border-gray-200 rounded-sm overflow-hidden">
            <div className="h-12 bg-[#fafafa] border-b border-gray-200 px-4 grid grid-cols-[3fr_1fr_2fr_1.5fr_1fr] items-center text-[14px] text-gray-500">
              <div>产品</div>
              <div>买家实付</div>
              <div>状态 / 倒计时</div>
              <div>物流渠道</div>
              <div>操作</div>
            </div>
            <div className="min-h-[420px] bg-white">
              {!loading && (data?.orders?.length ?? 0) === 0 && (
                <div className="h-[420px] flex items-center justify-center text-center">
                  <div>
                    <div className="mt-4 text-[15px] text-gray-400">暂无订单</div>
                    <button type="button" className="mt-1 text-[15px] text-[#3478f6] hover:underline">
                      点击刷新
                    </button>
                  </div>
                </div>
              )}

              {loading && (
                <div className="h-[420px] flex items-center justify-center text-[14px] text-gray-500">加载中...</div>
              )}

              {!loading &&
                (data?.orders ?? []).map((row) => {
                  const firstItem = row.items[0];
                  return (
                    <div key={row.id} className="border-b border-gray-100 p-4">
                      <div className="mb-3 -mx-1 rounded-sm border border-gray-100 bg-[#f6f6f6] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)]">
                        <div className="flex items-center justify-between text-[13px] text-gray-500">
                          <span className="inline-flex items-center gap-2">
                            {row.buyer_name}
                            {row.order_no.startsWith('SIM') && (
                              <span className="rounded-full bg-[#fff1ec] px-2 py-0.5 text-[11px] font-semibold text-[#ea580c]">
                                系统模拟
                              </span>
                            )}
                          </span>
                          <span>订单号 {row.order_no}</span>
                        </div>
                      </div>
                      <div className="grid grid-cols-[3fr_1fr_2fr_1.5fr_1fr] items-start text-[14px]">
                        <div className="flex items-start gap-3">
                          <img
                            src={firstItem?.image_url ?? 'https://picsum.photos/seed/shopee-fallback/80/80'}
                            className="w-14 h-14 rounded border border-gray-100 object-cover"
                            referrerPolicy="no-referrer"
                          />
                          <div>
                            <div className="text-gray-800">{firstItem?.product_name ?? '-'}</div>
                            <div className="text-[12px] text-gray-500 mt-1">
                              规格：{firstItem?.variant_name ?? '-'} · x{firstItem?.quantity ?? 0}
                            </div>
                          </div>
                        </div>
                        <div className="text-gray-800">{formatMoney(row.buyer_payment)}</div>
                        <div>
                          <div className="text-gray-800">{row.process_status === 'processing' ? '待处理' : '已处理'}</div>
                          <div className="text-[12px] text-gray-500 mt-1">{row.countdown_text}</div>
                        </div>
                        <div>
                          <div className="text-gray-800">{row.shipping_channel}</div>
                          <div className="text-[12px] text-gray-500 mt-1">MY线路</div>
                        </div>
                        <div className="flex flex-col items-start gap-1">
                          {buildOrderActions(row.action_text).map((action) => (
                            <button
                              key={action}
                              type="button"
                              className="text-[13px] leading-5 text-[#3478f6] hover:underline"
                            >
                              {action}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

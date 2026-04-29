import { useEffect, useMemo, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

interface DetailPerformance {
  total_sales_amount: number;
  total_orders_count: number;
  total_units_sold: number;
  total_buyers_count: number;
}

interface DetailItemRow {
  item_id: number;
  product_name: string;
  image_url: string | null;
  sku: string | null;
  original_price: number;
  discount_type: string;
  discount_type_label: string;
  discount_value: number;
  final_price: number | null;
  stock: number;
}

interface DetailDailyRow {
  stat_date: string;
  sales_amount: number;
  orders_count: number;
  units_sold: number;
  buyers_count: number;
}

interface DetailOrderRow {
  order_id: number;
  order_no: string;
  buyer_name: string;
  product_summary: string;
  buyer_payment: number;
  discount_percent: number | null;
  type_bucket: string;
  type_bucket_label: string;
  created_at: string;
}

interface RowList<T> {
  rows: T[];
  pagination: PaginationMeta;
}

interface DiscountDetailResponse {
  campaign_id: number;
  campaign_name: string;
  campaign_type: string;
  campaign_type_label: string;
  status: string;
  status_label: string;
  start_at: string | null;
  end_at: string | null;
  created_at: string;
  market: string;
  currency: string;
  performance: DetailPerformance;
  items: RowList<DetailItemRow>;
  daily_performance: RowList<DetailDailyRow>;
  orders: RowList<DetailOrderRow>;
}

interface DiscountDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  readOnly?: boolean;
  onBackToDiscount: () => void;
  onOpenOrderDetail: (orderId: number, tabType: string) => void;
}

const statusBadgeClassMap: Record<string, string> = {
  ongoing: 'bg-[#e9f8ef] text-[#1a9b50]',
  upcoming: 'bg-[#fff4df] text-[#b56b00]',
  ended: 'bg-[#eeeeee] text-[#777777]',
  disabled: 'bg-[#eeeeee] text-[#777777]',
  draft: 'bg-[#eef2ff] text-[#4f46e5]',
};

function formatMoney(value: number | null | undefined) {
  return `RM ${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDiscountBadge(row: DetailItemRow) {
  if (row.discount_type === 'percent') {
    const value = Number(row.discount_value || 0);
    return `${Number.isInteger(value) ? value : value.toFixed(1)}%OFF`;
  }
  return row.discount_type_label || '指定价';
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
    <div className="flex items-center justify-end gap-2 px-6 py-5 text-[13px] text-[#666]">
      <button
        type="button"
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
        className="h-8 min-w-8 border border-[#d8d8d8] bg-white px-2 text-[#666] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {'<'}
      </button>
      {pages.map((item, index) =>
        item === 'ellipsis' ? (
          <span key={`ellipsis-${index}`} className="px-1 text-[#999]">...</span>
        ) : (
          <button
            key={item}
            type="button"
            onClick={() => onPageChange(item)}
            className={`h-8 min-w-8 border px-2 ${item === currentPage ? 'border-[#ee4d2d] bg-[#ee4d2d] text-white' : 'border-[#d8d8d8] bg-white text-[#666] hover:border-[#ee4d2d] hover:text-[#ee4d2d]'}`}
          >
            {item}
          </button>
        ),
      )}
      <button
        type="button"
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        className="h-8 min-w-8 border border-[#d8d8d8] bg-white px-2 text-[#666] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {'>'}
      </button>
    </div>
  );
}

export default function DiscountDetailView({ runId, campaignId, readOnly = false, onBackToDiscount }: DiscountDetailViewProps) {
  const [detail, setDetail] = useState<DiscountDetailResponse | null>(null);
  const [items, setItems] = useState<RowList<DetailItemRow> | null>(null);
  const [productKeyword, setProductKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!runId || !campaignId) {
      setError('缺少活动信息，无法加载详情。');
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    let cancelled = false;
    const loadDetail = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/discount/campaigns/${campaignId}/detail`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('detail failed');
        const result = (await response.json()) as DiscountDetailResponse;
        if (cancelled) return;
        setDetail(result);
        setItems(result.items);
      } catch {
        if (!cancelled) setError('活动详情加载失败，请稍后重试。');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [campaignId, runId]);

  const loadItems = async (page: number) => {
    if (!runId || !campaignId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    setTableLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '10' });
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/discount/campaigns/${campaignId}/items?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('items failed');
      setItems((await response.json()) as RowList<DetailItemRow>);
    } catch {
      setError('商品列表加载失败，请稍后重试。');
    } finally {
      setTableLoading(false);
    }
  };

  const periodText = useMemo(() => {
    if (!detail) return '-';
    return `${detail.start_at || '-'} - ${detail.end_at || '-'}`;
  }, [detail]);

  const filteredRows = useMemo(() => {
    const keyword = productKeyword.trim().toLowerCase();
    const rows = items?.rows ?? [];
    if (!keyword) return rows;
    return rows.filter((row) => `${row.product_name} ${row.sku || ''}`.toLowerCase().includes(keyword));
  }, [items?.rows, productKeyword]);
  const isAddonCampaign = detail?.campaign_type === 'add_on' || detail?.campaign_type === 'gift';
  const priceColumnLabel = detail?.campaign_type === 'gift' ? '赠品价' : detail?.campaign_type === 'add_on' ? '加购价' : '折后价';
  const discountColumnLabel = isAddonCampaign ? '商品类型' : '折扣';

  return (
    <div className="flex-1 overflow-y-auto bg-[#f5f5f5] px-10 py-7 custom-scrollbar">
      <div className="mx-auto max-w-[1360px] pb-10">
        {error ? <div className="mb-4 border border-[#ffd6cc] bg-[#fff7f5] px-4 py-3 text-[13px] text-[#d63b1f]">{error}</div> : null}

        <section className="rounded-[4px] border border-[#e7e7e7] bg-white shadow-[0_1px_8px_rgba(0,0,0,0.08)]">
          <div className="px-8 pb-8 pt-7">
            <div className="flex items-center gap-3">
              <h1 className="text-[20px] font-semibold leading-none text-[#333]">基本信息</h1>
              {detail ? (
                <span className={`inline-flex h-6 items-center rounded-[2px] px-2 text-[13px] font-semibold ${statusBadgeClassMap[detail.status] ?? 'bg-[#eeeeee] text-[#777777]'}`}>
                  {detail.status_label}
                </span>
              ) : null}
              {readOnly ? <span className="ml-auto border border-amber-200 bg-amber-50 px-3 py-1 text-[12px] text-amber-700">历史回溯只读</span> : null}
            </div>

            <div className="mt-8 grid grid-cols-[1fr_1.1fr_1.35fr] gap-10 text-[16px] leading-6">
              <div className="min-w-0 whitespace-nowrap">
                <span className="text-[#888]">促销活动类型：</span>
                <span className="font-semibold text-[#333]">{detail?.campaign_type_label || '-'}</span>
              </div>
              <div className="min-w-0 whitespace-nowrap">
                <span className="text-[#888]">促销活动名称：</span>
                <span className="font-semibold text-[#333]">{loading ? '加载中...' : detail?.campaign_name || '-'}</span>
              </div>
              <div className="min-w-0 whitespace-nowrap">
                <span className="text-[#888]">促销活动时间：</span>
                <span className="font-semibold text-[#333]">{periodText}</span>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-5 rounded-[4px] border border-[#e5e5e5] bg-white">
          <div className="px-7 pb-3 pt-5">
            <h2 className="text-[18px] font-semibold text-[#333]">{isAddonCampaign ? '活动商品' : '折扣商品'}</h2>
            <div className="mt-4 flex h-8 w-[330px] items-center border border-[#d9d9d9] bg-white">
              <button type="button" className="flex h-full w-[130px] items-center justify-between border-r border-[#d9d9d9] px-3 text-[13px] text-[#333]">
                商品名称
                <span className="text-[10px] text-[#999]">⌄</span>
              </button>
              <input
                id="discount-product-search"
                value={productKeyword}
                onChange={(event) => setProductKeyword(event.target.value)}
                className="h-full min-w-0 flex-1 px-3 text-[13px] text-[#333] outline-none"
              />
              <button type="button" onClick={() => setProductKeyword('')} className="flex h-full w-9 items-center justify-center text-[16px] text-[#999] hover:text-[#ee4d2d]">
                ⌕
              </button>
            </div>
            <div className="mt-4 text-[13px] text-[#333]">
              共 {items?.pagination.total ?? 0} 个商品
              {tableLoading ? <span className="ml-3 text-[13px] text-[#999]">加载中...</span> : null}
            </div>
          </div>

          <div className="mx-7 border border-[#e5e5e5]">
            <div className="grid grid-cols-[minmax(360px,1.45fr)_160px_170px_150px_140px_170px_150px] bg-[#f7f7f7] px-5 py-3 text-[13px] font-normal text-[#555]">
              <div>商品名称</div>
              <div>原价</div>
              <div>{priceColumnLabel}</div>
              <div>{discountColumnLabel}</div>
              <div>库存 <span className="text-[#999]">ⓘ</span></div>
              <div>活动库存 <span className="text-[#999]">ⓘ</span></div>
              <div>购买限制 <span className="text-[#999]">ⓘ</span></div>
            </div>
            {filteredRows.length > 0 ? filteredRows.map((row) => (
              <div key={row.item_id} className="grid grid-cols-[minmax(360px,1.45fr)_160px_170px_150px_140px_170px_150px] border-t border-[#eeeeee] px-5 py-4 text-[13px] text-[#333]">
                <div className="flex min-w-0 items-center gap-3">
                  <div
                    className="flex h-[46px] w-[46px] flex-shrink-0 items-center justify-center border border-[#e1e1e1] bg-[#fafafa] text-[11px] text-[#999]"
                    style={row.image_url ? { backgroundImage: `url(${row.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}
                  >
                    {!row.image_url ? '图片' : ''}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-[#333]">{row.product_name}</div>
                    <div className="mt-1 truncate text-[12px] text-[#999]">SKU：{row.sku || '-'}</div>
                  </div>
                </div>
                <div className="pt-3 text-[#333]">{formatMoney(row.original_price)}</div>
                <div className="pt-3 text-[#333]">{row.final_price != null ? formatMoney(row.final_price) : '-'}</div>
                <div className="pt-2">
                  <span className="inline-flex h-5 items-center border border-[#ee4d2d] bg-white px-1.5 text-[11px] leading-none text-[#ee4d2d]">
                    {formatDiscountBadge(row)}
                  </span>
                </div>
                <div className="pt-3 text-[#333]">{Number(row.stock || 0)}</div>
                <div className="pt-3 text-[#333]">不限</div>
                <div className="pt-3 text-[#333]">不限</div>
              </div>
            )) : (
              <div className="border-t border-[#eeeeee] px-5 py-16 text-center text-[14px] text-[#999]">暂无商品</div>
            )}
          </div>

          {items ? <Pagination meta={items.pagination} onPageChange={(page) => loadItems(page)} /> : null}
        </section>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onBackToDiscount}
            className="h-10 min-w-[132px] border border-[#d9d9d9] bg-white px-6 text-[14px] font-medium text-[#555] hover:border-[#ee4d2d] hover:text-[#ee4d2d]"
          >
            返回列表页
          </button>
        </div>
      </div>
    </div>
  );
}

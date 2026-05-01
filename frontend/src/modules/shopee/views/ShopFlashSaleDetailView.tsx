import { useEffect, useMemo, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface ShopFlashSaleDetailViewProps {
  runId: number | null;
  campaignId: number | null;
  readOnly?: boolean;
  onBackToFlashSale: () => void;
}

interface FlashSaleProduct {
  listing_id: number;
  variant_id: number | null;
  product_name: string;
  variant_name: string;
  sku?: string | null;
  image_url?: string | null;
  original_price: number;
  flash_price?: number | null;
  activity_stock_limit?: number | null;
  stock_available: number;
  purchase_limit_per_buyer?: number | null;
  status: string;
  category_key?: string;
  category_label?: string;
}

interface FlashSaleDetail {
  id: number;
  campaign_name: string;
  display_time: string;
  status_label: string;
  enabled: boolean;
  items: FlashSaleProduct[];
}

interface CategoryRuleItem {
  label: string;
  value: string;
}

interface CategoryRulesResponse {
  categories: Array<{ key: string; label: string }>;
  category_rules: Record<string, CategoryRuleItem[]>;
}

function formatMoney(value: number | null | undefined): string {
  return `RM ${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function discountLabel(originalPrice: number, flashPrice: number | null | undefined): string {
  if (!originalPrice || !flashPrice || flashPrice >= originalPrice) return '-';
  return `${Math.round((1 - flashPrice / originalPrice) * 100)}%OFF`;
}

export default function ShopFlashSaleDetailView({ runId, campaignId, readOnly = false, onBackToFlashSale }: ShopFlashSaleDetailViewProps) {
  const [detail, setDetail] = useState<FlashSaleDetail | null>(null);
  const [categories, setCategories] = useState<Array<{ key: string; label: string }>>([]);
  const [categoryRules, setCategoryRules] = useState<Record<string, CategoryRuleItem[]>>({});
  const [activeCategory, setActiveCategory] = useState('all');

  useEffect(() => {
    if (!runId || !campaignId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const loadDetail = async () => {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/campaigns/${campaignId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const result = await response.json();
      if (!cancelled) setDetail(result);
    };
    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [campaignId, runId]);

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const loadRules = async () => {
      const categoryKey = detail?.items.find((item) => item.category_key)?.category_key;
      const query = categoryKey ? `?category_key=${encodeURIComponent(categoryKey)}` : '';
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/category-rules${query}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const result = (await response.json()) as CategoryRulesResponse;
      if (cancelled) return;
      setCategories(result.categories || []);
      setCategoryRules(result.category_rules || {});
    };
    void loadRules();
    return () => {
      cancelled = true;
    };
  }, [detail?.items, runId]);

  const productGroups = useMemo(() => {
    const groups = new Map<number, { listing_id: number; product_name: string; image_url?: string | null; purchase_limit_per_buyer?: number | null; variations: FlashSaleProduct[] }>();
    for (const item of detail?.items || []) {
      const existing = groups.get(item.listing_id);
      if (existing) {
        existing.variations.push(item);
      } else {
        groups.set(item.listing_id, {
          listing_id: item.listing_id,
          product_name: item.product_name,
          image_url: item.image_url,
          purchase_limit_per_buyer: item.purchase_limit_per_buyer,
          variations: [item],
        });
      }
    }
    return Array.from(groups.values()).map((group) => ({
      ...group,
      variations: [...group.variations].sort((a, b) => {
        if (a.status === b.status) return 0;
        return a.status === 'active' ? -1 : 1;
      }),
    }));
  }, [detail?.items]);

  const visibleCategories = useMemo(() => {
    const categoryKeys = new Set((detail?.items || []).map((item) => item.category_key).filter(Boolean));
    const matched = categories.filter((cat) => categoryKeys.has(cat.key));
    return matched.length > 0 ? matched : categories.filter((cat) => cat.key === 'all').slice(0, 1);
  }, [categories, detail?.items]);

  useEffect(() => {
    if (visibleCategories.length > 0 && !visibleCategories.some((cat) => cat.key === activeCategory)) {
      setActiveCategory(visibleCategories[0].key);
    }
  }, [activeCategory, visibleCategories]);

  const activeRules = categoryRules[activeCategory] || [];
  const activeItemCount = (detail?.items || []).filter((item) => item.status === 'active').length;
  const tableGridCols = 'grid-cols-[minmax(280px,2.5fr)_1fr_1.5fr_1fr_1.2fr_1fr_1fr_1fr] gap-x-2';

  return (
    <div className="flex-1 overflow-y-auto bg-[#f5f5f5] px-9 py-6 custom-scrollbar text-[#333] relative">
      <div className="mx-auto max-w-[1360px]">
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览详情页，但无法编辑活动。
          </div>
        )}

        <section className="bg-white px-8 py-7 shadow-sm border border-[#ebebeb] rounded-[2px]">
          <h2 className="text-[18px] font-medium text-[#333]">基础信息</h2>
          <div className="mt-8 grid grid-cols-[140px_1fr] items-start gap-y-8">
            <div className="pt-2 text-[14px] text-[#666] text-right pr-6">状态</div>
            <div className="pt-2 text-[14px] text-[#333]">{detail?.status_label || '-'}</div>

            <div className="pt-2 text-[14px] text-[#666] text-right pr-6">活动时间段</div>
            <div className="pt-2 text-[14px] text-[#333]">{detail?.display_time || '-'}</div>

            <div className="pt-3 text-[14px] text-[#666] text-right pr-6">商品条件</div>
            <div className="border border-[#ebebeb] rounded-sm p-6 max-w-[900px]">
              <div className="flex flex-wrap gap-3 mb-6">
                {visibleCategories.map((cat) => (
                  <button
                    key={cat.key}
                    type="button"
                    onClick={() => setActiveCategory(cat.key)}
                    className={`px-4 py-1.5 text-[14px] rounded-sm border ${
                      activeCategory === cat.key ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-[#ebebeb] text-[#333] hover:border-[#ccc]'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>

              <div>
                <h3 className="text-[14px] font-medium text-[#333] mb-4">
                  {visibleCategories.find((cat) => cat.key === activeCategory)?.label || '全部'} 商品条件
                </h3>
                <div className="grid grid-cols-2 gap-y-4 gap-x-8">
                  {activeRules.length > 0 ? activeRules.map((item) => (
                    <div key={`${item.label}-${item.value}`} className="flex items-center text-[13px] text-[#666]">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#ee4d2d] mr-2 shrink-0"></div>
                      <span>{item.label}: {item.value}</span>
                    </div>
                  )) : (
                    <div className="text-[13px] text-[#999]">暂无商品条件</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-5 bg-white px-8 py-7 shadow-sm border border-[#ebebeb] rounded-[2px]">
          <h2 className="text-[18px] font-medium text-[#333]">限时抢购商品</h2>
          <p className="mt-1 text-[13px] text-[#666]">
            您已为此限时抢购时间段启用 <span className="font-medium text-[#333]">{activeItemCount}</span> / 50 个商品。
          </p>

          <div className="mt-5">
            <div className={`grid ${tableGridCols} bg-[#fafafa] border border-[#ebebeb] rounded-sm px-5 py-3.5 text-[13px] text-[#666] font-medium`}>
              <div>商品变体</div>
              <div>原价</div>
              <div>折后价</div>
              <div>折扣</div>
              <div>活动库存</div>
              <div>库存</div>
              <div>订单限购</div>
              <div className="text-center">启用 / 停用</div>
            </div>

            {productGroups.length > 0 ? productGroups.map((group) => (
              <div key={group.listing_id} className="mt-3 border border-[#ebebeb] rounded-sm bg-white">
                <div className={`grid ${tableGridCols} items-center px-5 py-4 border-b border-[#ebebeb]`}>
                  <div className="flex items-center gap-3">
                    <div
                      className="w-12 h-12 bg-[#f5f5f5] border border-[#ebebeb] flex-shrink-0"
                      style={group.image_url ? { backgroundImage: `url(${group.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}
                    ></div>
                    <div className="text-[14px] text-[#333] font-medium truncate">{group.product_name}</div>
                  </div>
                  <div></div><div></div><div></div><div></div><div></div>
                  <div className="text-[13px] text-[#666]">{group.purchase_limit_per_buyer ? group.purchase_limit_per_buyer : '无限制'}</div>
                  <div></div>
                </div>

                <div className="px-5 py-2">
                  {group.variations.map((variant) => {
                    const disabled = variant.status !== 'active';
                    return (
                      <div key={`${variant.listing_id}-${variant.variant_id || 'default'}`} className={`grid ${tableGridCols} items-center py-3 text-[13px] ${disabled ? 'text-[#aaa] bg-[#fafafa]' : ''}`}>
                      <div className={`pl-[60px] pr-4 truncate ${disabled ? 'text-[#aaa]' : 'text-[#555]'}`}>{variant.variant_name || '默认款式'}</div>
                      <div className={disabled ? 'text-[#aaa]' : 'text-[#666]'}>{formatMoney(variant.original_price)}</div>
                      <div className={disabled ? 'text-[#aaa]' : 'text-[#333]'}>{formatMoney(variant.flash_price)}</div>
                      <div>
                        {discountLabel(variant.original_price, variant.flash_price) !== '-' ? (
                          <span className={`inline-block px-1.5 py-0.5 border text-[12px] font-medium leading-none rounded-sm ${disabled ? 'border-[#ddd] text-[#aaa] bg-[#f5f5f5]' : 'border-[#ff8b73] text-[#ee4d2d] bg-[#fff6f4]'}`}>
                            {discountLabel(variant.original_price, variant.flash_price)}
                          </span>
                        ) : '-'}
                      </div>
                      <div className={disabled ? 'text-[#aaa]' : 'text-[#333]'}>{variant.activity_stock_limit ?? '-'}</div>
                      <div className={disabled ? 'text-[#aaa]' : 'text-[#333]'}>{variant.stock_available}</div>
                      <div></div>
                      <div className={`text-center ${disabled ? 'text-[#aaa]' : 'text-[#333]'}`}>{variant.status === 'active' ? '启用' : '停用'}</div>
                    </div>
                    );
                  })}
                </div>

                <div className="bg-[#fafafa] border-t border-[#ebebeb] px-5 py-3.5 flex items-center justify-between rounded-b-sm">
                  <div className="text-[13px] text-[#05a]">{group.variations.filter((variant) => variant.status !== 'active').length} 个已停用变体</div>
                  <div className="text-[13px] text-[#666]">共 {group.variations.length} 个变体</div>
                </div>
              </div>
            )) : (
              <div className="border-x border-b border-[#ebebeb] px-5 py-10 text-center text-[13px] text-[#999]">暂无活动商品</div>
            )}
          </div>
        </section>

        <div className="mt-6 flex items-center justify-end gap-3">
          <button type="button" onClick={onBackToFlashSale} className="h-9 border border-[#d9d9d9] bg-white px-6 text-[14px] text-[#333] rounded-sm hover:bg-[#fafafa]">
            返回
          </button>
        </div>
      </div>
    </div>
  );
}

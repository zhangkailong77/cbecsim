import { useEffect, useMemo, useState } from 'react';
import DateTimePicker from '../components/DateTimePicker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type DiscountType = 'fixed_amount' | 'percent';
type MaxDiscountType = 'set_amount' | 'no_limit';
type ProductPickerTab = 'select' | 'upload';
type ProductPickerSearchField = 'product_name' | 'product_id';

interface VideoVoucherCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  detailCampaignId?: number | null;
  onBackToVouchers: () => void;
}

interface VoucherPickerProduct {
  listing_id: number;
  variant_id: number | null;
  variant_ids?: number[];
  product_name: string;
  variant_name?: string;
  sku?: string | null;
  image_url?: string | null;
  category_key?: string;
  category_label?: string;
  original_price: number;
  price_range_label?: string | null;
  stock_available: number;
}

interface EligibleProductsResponse {
  items: VoucherPickerProduct[];
}

interface VoucherDetailResponse extends VoucherCreateBootstrapResponse {
  selected_products: VoucherPickerProduct[];
}

interface VoucherCreateBootstrapResponse {
  meta: {
    read_only: boolean;
    currency: string;
  };
  form: {
    voucher_name: string;
    start_at: string;
    end_at: string;
    display_before_start: boolean;
    display_start_at: string | null;
    discount_type: DiscountType;
    discount_amount: number | null;
    discount_percent: number | null;
    max_discount_type: MaxDiscountType;
    max_discount_amount: number | null;
    min_spend_amount: number | null;
    usage_limit: number | null;
    per_buyer_limit: number;
    applicable_scope: string;
  };
}

const voucherIllustrationUrl = 'https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/mmf_portal_seller_root_dir/static/modules/vouchers-v2/image/voucher_video_preview_th.3327e7d.png';

const PlusIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"></line>
    <line x1="5" y1="12" x2="19" y2="12"></line>
  </svg>
);

const CloseIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-[#999] hover:text-[#333]">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
);

const TrashIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18"></path>
    <path d="M8 6V4h8v2"></path>
    <path d="M19 6l-1 14H6L5 6"></path>
    <path d="M10 11v5"></path>
    <path d="M14 11v5"></path>
  </svg>
);

const PackageOpenIcon = () => (
  <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9.5 12 4l9 5.5-9 5.5L3 9.5Z"></path>
    <path d="M3 9.5V15l9 5 9-5V9.5"></path>
    <path d="M12 15v5"></path>
  </svg>
);

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function buildDefaultDisplayStartAt(voucherStartAt: string): string {
  if (!voucherStartAt) return '';
  const [datePart, timePart = '00:00'] = voucherStartAt.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute] = timePart.split(':').map(Number);
  if (!year || !month || !day) return '';
  const displayDate = new Date(year, month - 1, day, Number.isFinite(hour) ? hour : 0, Number.isFinite(minute) ? minute : 0);
  displayDate.setHours(displayDate.getHours() - 1);
  return `${displayDate.getFullYear()}-${pad2(displayDate.getMonth() + 1)}-${pad2(displayDate.getDate())}T${pad2(displayDate.getHours())}:${pad2(displayDate.getMinutes())}`;
}

export default function VideoVoucherCreateView({ runId, readOnly = false, detailCampaignId = null, onBackToVouchers }: VideoVoucherCreateViewProps) {
  const [voucherName, setVoucherName] = useState('');
  const [voucherStartAt, setVoucherStartAt] = useState('');
  const [voucherEndAt, setVoucherEndAt] = useState('');
  const [displayBeforeStart, setDisplayBeforeStart] = useState(false);
  const [displayStartAt, setDisplayStartAt] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [discountType, setDiscountType] = useState<DiscountType>('fixed_amount');
  const [maxDiscountType, setMaxDiscountType] = useState<MaxDiscountType>('set_amount');
  const [discountAmount, setDiscountAmount] = useState('');
  const [discountPercent, setDiscountPercent] = useState('');
  const [maxDiscountAmount, setMaxDiscountAmount] = useState('');
  const [minSpendAmount, setMinSpendAmount] = useState('');
  const [usageLimit, setUsageLimit] = useState('');
  const [perBuyerLimit, setPerBuyerLimit] = useState('1');
  const [applicableProductType, setApplicableProductType] = useState<'all' | 'specific'>('all');
  const [selectedProducts, setSelectedProducts] = useState<VoucherPickerProduct[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [currency, setCurrency] = useState('RM');

  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTab, setPickerTab] = useState<ProductPickerTab>('select');
  const [pickerRows, setPickerRows] = useState<VoucherPickerProduct[]>([]);
  const [pickerSelections, setPickerSelections] = useState<Record<string, VoucherPickerProduct>>({});
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState('');
  const [pickerKeywordInput, setPickerKeywordInput] = useState('');
  const [pickerKeyword, setPickerKeyword] = useState('');
  const [pickerSearchField, setPickerSearchField] = useState<ProductPickerSearchField>('product_name');
  const [pickerCategory, setPickerCategory] = useState('all');
  const [pickerAvailableOnly, setPickerAvailableOnly] = useState(true);

  const effectiveReadOnly = readOnly || serverReadOnly;
  const pickerRowKey = (item: VoucherPickerProduct) => `${item.listing_id}-${item.variant_id ?? 0}`;
  const formatMoney = (value: number) => `${currency} ${Number(value || 0).toFixed(0)}`;

  const categoryOptions = useMemo(() => {
    const map = new Map<string, string>();
    pickerRows.forEach((item) => {
      const key = item.category_key || item.category_label || '未分类';
      map.set(key, item.category_label || key);
    });
    return [{ value: 'all', label: '全部' }, ...Array.from(map.entries()).map(([value, label]) => ({ value, label }))];
  }, [pickerRows]);

  const handleDisplayBeforeStartChange = (checked: boolean) => {
    setDisplayBeforeStart(checked);
    if (checked && !displayStartAt) {
      setDisplayStartAt(buildDefaultDisplayStartAt(voucherStartAt));
    }
  };

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setError('');
    const endpoint = detailCampaignId
      ? `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/detail/video_voucher/${detailCampaignId}`
      : `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/video-create/bootstrap`;
    fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) {
          const result = await response.json().catch(() => null);
          throw new Error(result?.detail || (detailCampaignId ? '详情页加载失败，请稍后重试。' : '创建页初始化失败，请稍后重试。'));
        }
        return response.json() as Promise<VoucherCreateBootstrapResponse | VoucherDetailResponse>;
      })
      .then((result) => {
        if (cancelled) return;
        setServerReadOnly(Boolean(result.meta.read_only || detailCampaignId));
        setCurrency(result.meta.currency || 'RM');
        setVoucherName(result.form.voucher_name || '');
        if ('selected_products' in result) {
          setSelectedProducts(result.selected_products || []);
        }
        const nextStartAt = result.form.start_at || '';
        const nextDisplayBeforeStart = Boolean(result.form.display_before_start);
        setVoucherStartAt(nextStartAt);
        setVoucherEndAt(result.form.end_at || '');
        setDisplayBeforeStart(nextDisplayBeforeStart);
        setDisplayStartAt(result.form.display_start_at || (nextDisplayBeforeStart ? buildDefaultDisplayStartAt(nextStartAt) : ''));
        setDiscountType(result.form.discount_type || 'fixed_amount');
        setDiscountAmount(result.form.discount_amount == null ? '' : String(result.form.discount_amount));
        setDiscountPercent(result.form.discount_percent == null ? '' : String(result.form.discount_percent));
        setMaxDiscountType(result.form.max_discount_type || 'set_amount');
        setMaxDiscountAmount(result.form.max_discount_amount == null ? '' : String(result.form.max_discount_amount));
        setMinSpendAmount(result.form.min_spend_amount == null ? '' : String(result.form.min_spend_amount));
        setUsageLimit(result.form.usage_limit == null ? '' : String(result.form.usage_limit));
        setPerBuyerLimit(String(result.form.per_buyer_limit || 1));
        setApplicableProductType(result.form.applicable_scope === 'selected_products' ? 'specific' : 'all');
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : (detailCampaignId ? '详情页加载失败，请稍后重试。' : '创建页初始化失败，请稍后重试。'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, detailCampaignId]);

  useEffect(() => {
    if (!pickerOpen || pickerTab !== 'select' || !runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPickerLoading(true);
      setPickerError('');
      try {
        const params = new URLSearchParams({
          keyword: pickerKeyword,
          search_field: pickerSearchField,
          category_key: pickerCategory,
          available_only: pickerAvailableOnly ? 'true' : 'false',
          page: '1',
          page_size: '20',
        });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/video-create/eligible-products?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('eligible products failed');
        const result = (await response.json()) as EligibleProductsResponse;
        if (!cancelled) setPickerRows(result.items || []);
      } catch {
        if (!cancelled) {
          setPickerRows([]);
          setPickerError('商品列表加载失败，请稍后重试。');
        }
      } finally {
        if (!cancelled) setPickerLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [pickerAvailableOnly, pickerCategory, pickerKeyword, pickerOpen, pickerSearchField, pickerTab, runId]);

  const handleOpenPicker = () => {
    setPickerSelections(Object.fromEntries(selectedProducts.map((item) => [pickerRowKey(item), item])));
    setPickerOpen(true);
    setPickerTab('select');
  };

  const handleConfirmPicker = () => {
    setSelectedProducts(Object.values(pickerSelections).slice(0, 100));
    setPickerOpen(false);
  };

  const validateForm = () => {
    if (!voucherName.trim()) return '请输入代金券名称。';
    if (!voucherStartAt || !voucherEndAt) return '请选择代金券使用期限。';
    if (voucherStartAt >= voucherEndAt) return '代金券结束时间必须晚于开始时间。';
    if (displayBeforeStart) {
      if (!displayStartAt) return '请选择提前展示时间。';
      if (displayStartAt >= voucherStartAt) return '提前展示时间必须早于代金券开始时间。';
    }
    const minSpend = Number(minSpendAmount);
    const usage = Number(usageLimit);
    const perBuyer = Number(perBuyerLimit);
    if (!Number.isFinite(minSpend) || minSpend <= 0) return '最低消费金额必须大于 0。';
    if (discountType === 'fixed_amount') {
      const amount = Number(discountAmount);
      if (!Number.isFinite(amount) || amount <= 0) return '优惠金额必须大于 0。';
      if (minSpend < amount) return '最低消费金额不能小于优惠金额。';
    } else {
      const percent = Number(discountPercent);
      if (!Number.isFinite(percent) || percent <= 0 || percent > 100) return '优惠百分比必须大于 0 且不超过 100。';
      if (maxDiscountType === 'set_amount') {
        const maxAmount = Number(maxDiscountAmount);
        if (!Number.isFinite(maxAmount) || maxAmount <= 0) return '最大折扣金额必须大于 0。';
      }
    }
    if (!Number.isInteger(usage) || usage <= 0) return '使用数量必须为正整数。';
    if (!Number.isInteger(perBuyer) || perBuyer <= 0 || perBuyer > usage) return '每位买家最大发放量必须为正整数且不超过使用数量。';
    if (applicableProductType === 'specific' && !selectedProducts.length) return '请至少选择一个适用商品。';
    if (applicableProductType === 'specific' && selectedProducts.length > 100) return '最多选择 100 个适用商品。';
    return '';
  };

  const handleSubmit = async () => {
    if (!runId || effectiveReadOnly || saving) return;
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    setSaving(true);
    setError('');
    try {
      const selectedProductsPayload = applicableProductType === 'specific' ? selectedProducts.flatMap((item) => {
        if (item.variant_ids?.length) {
          return item.variant_ids.map((variantId) => ({ listing_id: item.listing_id, variant_id: variantId }));
        }
        return [{ listing_id: item.listing_id, variant_id: item.variant_id }];
      }) : [];
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/video-campaigns`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voucher_type: 'video_voucher',
          voucher_name: voucherName.trim(),
          start_at: voucherStartAt,
          end_at: voucherEndAt,
          display_before_start: displayBeforeStart,
          display_start_at: displayBeforeStart ? displayStartAt : null,
          reward_type: 'discount',
          discount_type: discountType,
          discount_amount: discountType === 'fixed_amount' ? Number(discountAmount) : null,
          discount_percent: discountType === 'percent' ? Number(discountPercent) : null,
          max_discount_type: discountType === 'percent' ? maxDiscountType : 'set_amount',
          max_discount_amount: discountType === 'percent' && maxDiscountType === 'set_amount' ? Number(maxDiscountAmount) : null,
          min_spend_amount: Number(minSpendAmount),
          usage_limit: Number(usageLimit),
          per_buyer_limit: Number(perBuyerLimit),
          display_type: 'video_stream',
          display_channels: ['shopee_video'],
          applicable_scope: applicableProductType === 'specific' ? 'selected_products' : 'all_products',
          video_scope: 'all_videos',
          selected_products: selectedProductsPayload,
        }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        throw new Error(result?.detail || '创建失败，请稍后重试。');
      }
      onBackToVouchers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败，请稍后重试。');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] custom-scrollbar text-[#333] flex flex-col">
      <div className="mx-auto w-full max-w-[1440px] px-6 pt-6 pb-6 flex-1 flex flex-col relative">
        {effectiveReadOnly && !detailCampaignId && (
          <div className="mb-4 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700 shrink-0">
            当前为历史对局回溯模式：可浏览创建页，但无法创建代金券。
          </div>
        )}
        {error && <div className="mb-4 border border-red-200 bg-red-50 px-4 py-2 text-[13px] text-red-600 shrink-0">{error}</div>}

        <div className="flex items-start gap-6 shrink-0 h-full">
          <div className="flex-1 min-w-[800px] flex flex-col relative">
            <div className="flex flex-col gap-4 pb-6">
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">基础信息</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-2 text-right pr-6">代金券类型</div>
                  <div>
                    <div className="relative flex h-[40px] w-[180px] items-center justify-center rounded-sm border border-[#ee4d2d] bg-white text-[#ee4d2d] cursor-pointer">
                      <svg viewBox="0 0 24 24" className="mr-2 h-[18px] w-[18px]" fill="currentColor">
                        <path fillRule="evenodd" clipRule="evenodd" d="M4 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H4zm6 3.5v7l6-3.5-6-3.5z" />
                      </svg>
                      视频代金券
                      <div className="absolute right-0 top-0 h-0 w-0 border-l-[16px] border-t-[16px] border-l-transparent border-t-[#ee4d2d]"></div>
                      <svg className="absolute right-[1px] top-[1px] h-[10px] w-[10px] text-white" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M13.485 1.431a1.473 1.473 0 0 1 2.104 2.062l-7.84 9.802a1.473 1.473 0 0 1-2.12.04L.431 8.138a1.473 1.473 0 0 1 2.084-2.083l4.111 4.112 6.82-8.65a.486.486 0 0 1 .04-.086z" />
                      </svg>
                    </div>
                  </div>

                  <div className="pt-2 text-right pr-6">代金券名称</div>
                  <div className="max-w-[700px]">
                    <div className="flex h-9 w-full items-center rounded-sm border border-[#e5e5e5] px-3 focus-within:border-[#ee4d2d]">
                      <input type="text" value={voucherName} onChange={(e) => setVoucherName(e.target.value.slice(0, 100))} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] disabled:bg-white" placeholder="请输入" />
                      <span className="text-[12px] text-[#999]">{voucherName.length}/100</span>
                    </div>
                    <div className="mt-2 text-[12px] text-[#999]">代金券名称仅卖家可见，不向买家展示。</div>
                  </div>

                  <div className="pt-2 text-right pr-6">代金券使用期限</div>
                  <div className="max-w-[700px]">
                    <div className="flex items-center gap-3">
                      <DateTimePicker value={voucherStartAt} onChange={effectiveReadOnly ? () => undefined : setVoucherStartAt} inputWidthClassName="w-[180px]" popupPlacement="bottom" maxValue={voucherEndAt || undefined} />
                      <span className="w-[18px] text-center text-[14px] text-[#999]">至</span>
                      <DateTimePicker value={voucherEndAt} onChange={effectiveReadOnly ? () => undefined : setVoucherEndAt} inputWidthClassName="w-[180px]" popupPlacement="bottom" minValue={voucherStartAt || undefined} />
                    </div>
                    <div className="mt-2 text-[12px] text-[#999]">这里显示和提交的时间均为当前对局的游戏时间。</div>
                    <label className="mt-4 flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={displayBeforeStart} onChange={(e) => handleDisplayBeforeStartChange(e.target.checked)} disabled={effectiveReadOnly} className="h-[14px] w-[14px] accent-[#ee4d2d]" />
                      <span className="text-[14px] text-[#333]">提前展示代金券</span>
                    </label>
                    {displayBeforeStart && (
                      <div className="mt-3 ml-6 max-w-[400px]">
                        <DateTimePicker value={displayStartAt} onChange={effectiveReadOnly ? () => undefined : setDisplayStartAt} inputWidthClassName="w-full" popupPlacement="bottom" maxValue={voucherStartAt || undefined} />
                        <div className="mt-2 text-[12px] text-[#999] leading-relaxed">代金券开始展示后，此部分将无法再次编辑。</div>
                      </div>
                    )}
                  </div>
                </div>
              </section>

              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">奖励设置</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-1 text-right pr-6">奖励类型</div>
                  <div className="flex items-center gap-6"><label className="flex items-center gap-2 cursor-pointer"><input type="radio" name="videoRewardType" checked readOnly className="h-4 w-4 accent-[#ee4d2d]" /><span>折扣</span></label></div>

                  <div className="pt-2 text-right pr-6">折扣类型 | 金额</div>
                  <div className="flex items-center gap-3 max-w-[700px]">
                    <div className={`relative h-9 w-[160px] rounded-sm border ${isDropdownOpen ? 'border-[#ee4d2d]' : 'border-[#e5e5e5]'} px-3 flex items-center justify-between cursor-pointer bg-white`} onClick={() => !effectiveReadOnly && setIsDropdownOpen(!isDropdownOpen)}>
                      <span>{discountType === 'fixed_amount' ? '固定金额' : '百分比'}</span>
                      <span className="text-[10px] text-[#999] transition-transform duration-200" style={{ transform: isDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
                      {isDropdownOpen && (
                        <div className="absolute left-[-1px] top-[100%] z-20 mt-1 w-[160px] rounded-sm border border-[#e5e5e5] bg-white py-1 shadow-[0_2px_8px_rgba(0,0,0,0.12)]">
                          <div className={`px-3 py-[6px] hover:bg-[#f6f6f6] ${discountType === 'percent' ? 'text-[#ee4d2d]' : 'text-[#333]'}`} onClick={(e) => { e.stopPropagation(); setDiscountType('percent'); setIsDropdownOpen(false); }}>百分比</div>
                          <div className={`px-3 py-[6px] hover:bg-[#f6f6f6] ${discountType === 'fixed_amount' ? 'text-[#ee4d2d]' : 'text-[#333]'}`} onClick={(e) => { e.stopPropagation(); setDiscountType('fixed_amount'); setIsDropdownOpen(false); }}>固定金额</div>
                        </div>
                      )}
                    </div>
                    <div className="flex h-9 w-[280px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                      {discountType === 'fixed_amount' && <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>}
                      <input type="number" value={discountType === 'fixed_amount' ? discountAmount : discountPercent} onChange={(e) => discountType === 'fixed_amount' ? setDiscountAmount(e.target.value) : setDiscountPercent(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" />
                      {discountType === 'percent' && <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-l border-[#e5e5e5] text-[#999] text-[12px]">%OFF</div>}
                    </div>
                  </div>

                  {discountType === 'percent' && (<>
                    <div className="pt-2 text-right pr-6">最大折扣金额</div>
                    <div className="max-w-[700px] flex flex-col gap-3">
                      <div className="flex items-center gap-6 mt-2">
                        <label className="flex items-center gap-2 cursor-pointer"><input type="radio" name="maxDiscount" checked={maxDiscountType === 'set_amount'} onChange={() => setMaxDiscountType('set_amount')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" /><span>设置金额</span></label>
                        <label className="flex items-center gap-2 cursor-pointer"><input type="radio" name="maxDiscount" checked={maxDiscountType === 'no_limit'} onChange={() => setMaxDiscountType('no_limit')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" /><span>无限制</span></label>
                      </div>
                      {maxDiscountType === 'set_amount' && <div className="flex h-9 w-[452px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden"><div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div><input type="number" value={maxDiscountAmount} onChange={(e) => setMaxDiscountAmount(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" /></div>}
                    </div>
                  </>)}

                  <div className="pt-2 text-right pr-6">最低消费金额</div>
                  <div className="max-w-[700px]"><div className="flex h-9 w-[452px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden"><div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div><input type="number" value={minSpendAmount} onChange={(e) => setMinSpendAmount(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" /></div></div>

                  <div className="pt-2 text-right pr-6">使用数量</div>
                  <div className="max-w-[700px]"><input type="number" value={usageLimit} onChange={(e) => setUsageLimit(e.target.value)} disabled={effectiveReadOnly} className="h-9 w-[452px] rounded-sm border border-[#e5e5e5] px-3 text-[14px] outline-none focus:border-[#ee4d2d] disabled:bg-white" /><div className="mt-2 text-[12px] text-[#999]">所有买家可使用的代金券总数</div></div>

                  <div className="pt-2 text-right pr-6 flex items-center justify-end gap-1">每位买家最大发放量<span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px]">?</span></div>
                  <div className="max-w-[700px]"><input type="number" value={perBuyerLimit} onChange={(e) => setPerBuyerLimit(e.target.value)} disabled={effectiveReadOnly} className="h-9 w-[452px] rounded-sm border border-[#e5e5e5] px-3 text-[14px] outline-none focus:border-[#ee4d2d] disabled:bg-white" /></div>
                </div>
              </section>

              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">代金券展示与适用商品</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-1 text-right pr-6">代金券展示设置</div>
                  <div className="text-[#333] pt-1">仅在 Shopee 视频展示</div>

                  <div className="pt-1 text-right pr-6">适用商品</div>
                  <div className="flex flex-col gap-4 max-w-[760px]">
                    <div>
                      <label className="flex items-center gap-2 cursor-pointer"><input type="radio" name="applicableProduct" checked={applicableProductType === 'all'} onChange={() => setApplicableProductType('all')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" /><span>全部商品</span></label>
                      {applicableProductType === 'all' && <div className="ml-6 mt-1 text-[12px] text-[#eda500] leading-relaxed max-w-[600px]">仅限选定商品。受您所在国家/地区的法规或平台会员专属规则影响，部分商品禁止参与促销活动。</div>}
                    </div>
                    <div>
                      <label className="flex items-center gap-2 cursor-pointer"><input type="radio" name="applicableProduct" checked={applicableProductType === 'specific'} onChange={() => setApplicableProductType('specific')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" /><span>指定商品</span></label>
                      {applicableProductType === 'specific' && (
                        <div className="ml-6 mt-4">
                          {selectedProducts.length > 0 ? (
                            <div className="mb-3 flex items-center justify-between">
                              <div className="text-[14px] text-[#555]">已选择 <span className="mx-1 font-medium text-[#333]">{selectedProducts.length}</span><span className="text-[#999]">件商品</span></div>
                              <button type="button" onClick={handleOpenPicker} disabled={effectiveReadOnly} className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-[#ee4d2d] px-4 text-[13px] text-[#ee4d2d] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed"><PlusIcon />添加商品</button>
                            </div>
                          ) : (
                            <button type="button" onClick={handleOpenPicker} disabled={effectiveReadOnly} className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-[#ee4d2d] px-4 text-[13px] text-[#ee4d2d] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed"><PlusIcon />添加商品</button>
                          )}

                          {selectedProducts.length > 0 && (
                            <div className="overflow-hidden rounded-sm border border-[#e5e5e5] bg-white">
                              <div className="grid grid-cols-[1fr_130px_100px_80px] items-center bg-[#f5f5f5] px-4 py-3 text-[13px] text-[#666]"><div>商品</div><div className="text-right">原价</div><div className="text-right">库存</div><div className="text-center">操作</div></div>
                              <div className="max-h-[330px] overflow-y-auto px-4 custom-scrollbar">
                                {selectedProducts.map((item) => (
                                  <div key={pickerRowKey(item)} className="grid grid-cols-[1fr_130px_100px_80px] items-center border-t border-[#f1f1f1] py-3 text-[14px] text-[#444] first:border-t-0">
                                    <div className="flex min-w-0 items-center gap-3 pr-4"><div className="h-10 w-10 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5]" style={item.image_url ? { backgroundImage: `url(${item.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined} /><div className="min-w-0"><div className="truncate text-[#333]">{item.product_name}</div><div className="mt-1 text-[12px] text-[#999]">ID: {item.listing_id}{item.variant_ids?.length ? ` / ${item.variant_ids.length} 个变体` : ''}</div></div></div>
                                    <div className="text-right">{item.price_range_label || formatMoney(item.original_price)}</div>
                                    <div className="text-right">{item.stock_available}</div>
                                    <button type="button" disabled={effectiveReadOnly} onClick={() => setSelectedProducts((prev) => prev.filter((row) => pickerRowKey(row) !== pickerRowKey(item)))} className="mx-auto flex h-8 w-8 items-center justify-center text-[#999] hover:text-[#ee4d2d] disabled:cursor-not-allowed disabled:opacity-50"><TrashIcon /></button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </section>
            </div>

            <div className="sticky bottom-0 z-40 mt-auto rounded-t-[4px] border-t border-l border-r border-[#ececec] bg-white px-8 py-3 shadow-[0_-4px_16px_rgba(0,0,0,0.04)]">
              <div className="flex items-center justify-end gap-4">
                <button type="button" onClick={onBackToVouchers} className="h-8 min-w-[80px] rounded-sm border border-[#e5e5e5] bg-white px-6 text-[14px] text-[#333] hover:bg-[#fafafa]">取消</button>
                <button type="button" onClick={handleSubmit} disabled={effectiveReadOnly || loading || saving} className="h-8 min-w-[80px] rounded-sm bg-[#ee4d2d] px-6 text-[14px] text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899]">{saving ? '提交中...' : '确认'}</button>
              </div>
            </div>
          </div>

          <div className="w-[320px] shrink-0 sticky top-0">
            <div className="border border-[#ececec] bg-white p-5 shadow-sm rounded-[2px]">
              <div className="text-[16px] font-medium text-[#333] mb-4">预览</div>
              <div className="mx-auto h-[310px] w-full bg-top bg-no-repeat bg-contain" style={{ backgroundImage: `url("${voucherIllustrationUrl}")` }}></div>
              <div className="mt-4 text-[11px] text-[#999] text-center px-4">买家仅可在通过 Shopee 视频添加的商品上使用此代金券。</div>
            </div>
          </div>
        </div>
      </div>

      {pickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.32)]">
          <div className="flex h-[676px] w-[950px] flex-col border border-[#ececec] bg-white shadow-[0_18px_60px_rgba(15,23,42,0.22)]">
            <div className="flex items-center justify-between px-6 pb-2 pt-6">
              <div className="text-[20px] font-medium text-[#333]">添加商品</div>
              <button type="button" onClick={() => setPickerOpen(false)}><CloseIcon /></button>
            </div>
            <div className="flex gap-8 border-b border-[#ececec] px-6 text-[15px]">
              <button type="button" onClick={() => setPickerTab('select')} className={`border-b-2 py-3 ${pickerTab === 'select' ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#555]'}`}>选择商品</button>
              <button type="button" onClick={() => setPickerTab('upload')} className={`border-b-2 py-3 ${pickerTab === 'upload' ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#555]'}`}>上传商品列表</button>
            </div>
            {pickerTab === 'select' ? (
              <div className="flex min-h-0 flex-1 flex-col px-6 py-4">
                <div className="mb-4 flex items-center gap-3 text-[14px]">
                  <select value={pickerCategory} onChange={(e) => setPickerCategory(e.target.value)} className="h-9 w-[160px] rounded-sm border border-[#d8d8d8] px-3 outline-none focus:border-[#ee4d2d]">
                    {categoryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                  <select value={pickerSearchField} onChange={(e) => setPickerSearchField(e.target.value as ProductPickerSearchField)} className="h-9 w-[130px] rounded-sm border border-[#d8d8d8] px-3 outline-none focus:border-[#ee4d2d]"><option value="product_name">商品名称</option><option value="product_id">商品 ID</option></select>
                  <input value={pickerKeywordInput} onChange={(e) => setPickerKeywordInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') setPickerKeyword(pickerKeywordInput.trim()); }} className="h-9 flex-1 rounded-sm border border-[#d8d8d8] px-3 outline-none focus:border-[#ee4d2d]" placeholder="请输入关键词" />
                  <button type="button" onClick={() => setPickerKeyword(pickerKeywordInput.trim())} className="h-9 rounded-sm bg-[#ee4d2d] px-5 text-white hover:bg-[#d83f21]">搜索</button>
                  <label className="flex items-center gap-2 whitespace-nowrap text-[13px] text-[#666]"><input type="checkbox" checked={pickerAvailableOnly} onChange={(e) => setPickerAvailableOnly(e.target.checked)} className="accent-[#ee4d2d]" />仅显示可参与活动商品</label>
                </div>
                <div className="grid grid-cols-[44px_1fr_130px_110px] bg-[#f5f5f5] px-4 py-3 text-[13px] text-[#666]"><div></div><div>商品</div><div className="text-right">原价</div><div className="text-right">库存</div></div>
                <div className="min-h-0 flex-1 overflow-y-auto border border-t-0 border-[#ececec] px-4 custom-scrollbar">
                  {pickerLoading ? <div className="flex h-full items-center justify-center text-[#999]">加载中...</div> : pickerError ? <div className="flex h-full items-center justify-center text-red-500">{pickerError}</div> : pickerRows.length ? pickerRows.map((item) => {
                    const key = pickerRowKey(item);
                    return (
                      <div key={key} className="grid grid-cols-[44px_1fr_130px_110px] items-center border-t border-[#f1f1f1] py-3 text-[14px] first:border-t-0">
                        <input type="checkbox" checked={Boolean(pickerSelections[key])} onChange={(e) => setPickerSelections((prev) => { const next = { ...prev }; if (e.target.checked) next[key] = item; else delete next[key]; return next; })} className="h-4 w-4 accent-[#ee4d2d]" />
                        <div className="flex min-w-0 items-center gap-3 pr-4"><div className="h-10 w-10 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5]" style={item.image_url ? { backgroundImage: `url(${item.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined} /><div className="min-w-0"><div className="truncate text-[#333]">{item.product_name}</div><div className="mt-1 text-[12px] text-[#999]">ID: {item.listing_id}{item.variant_ids?.length ? ` / ${item.variant_ids.length} 个变体` : ''}</div></div></div>
                        <div className="text-right">{item.price_range_label || formatMoney(item.original_price)}</div>
                        <div className="text-right">{item.stock_available}</div>
                      </div>
                    );
                  }) : <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-[#9a9a9a]"><div className="flex h-16 w-16 items-center justify-center border border-[#ededed] bg-[#fafafa] text-[#d6d6d6]"><PackageOpenIcon /></div><div className="text-[14px]">未找到符合条件的商品</div></div>}
                </div>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 text-[#999]"><PackageOpenIcon /><div>上传商品列表功能将在后续阶段接入。</div></div>
            )}
            <div className="flex items-center justify-between border-t border-[#ececec] px-6 py-4">
              <div className="text-[13px] text-[#999]">已选择 {Object.keys(pickerSelections).length} 件商品</div>
              <div className="flex gap-3"><button type="button" onClick={() => setPickerOpen(false)} className="h-9 rounded-sm border border-[#d8d8d8] px-6 text-[#555] hover:bg-[#fafafa]">取消</button><button type="button" onClick={handleConfirmPicker} className="h-9 rounded-sm bg-[#ee4d2d] px-6 text-white hover:bg-[#d83f21]">确认</button></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

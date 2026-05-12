import { useEffect, useMemo, useState } from 'react';
import DateTimePicker from '../components/DateTimePicker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type ProductPickerTab = 'select' | 'upload';
type ProductPickerSearchField = 'product_name' | 'product_id';
type ProductPickerDropdown = 'category' | 'search_field' | null;
type ProductPickerCategoryParent = 'shopee' | 'shop' | null;
type DisplayType = 'all_pages' | 'specific_channels' | 'code_only';
type DiscountType = 'fixed_amount' | 'percent';
type MaxDiscountType = 'set_amount' | 'no_limit';

interface ProductPickerCategoryOption {
  value: string;
  label: string;
  accent?: boolean;
  hasChild?: boolean;
}

interface ProductVoucherCreateViewProps {
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
  image_url?: string | null;
  category_key?: string;
  category_label?: string;
  original_price: number;
  price_range_label?: string | null;
  stock_available: number;
  likes_count?: number;
  conflict?: boolean;
  conflict_reason?: string | null;
}

interface EligibleProductsResponse {
  items: VoucherPickerProduct[];
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
    display_type: DisplayType;
    display_channels: string[];
  };
}

interface VoucherCodeCheckResponse {
  available: boolean;
  message: string;
}

interface VoucherDetailResponse extends VoucherCreateBootstrapResponse {
  voucher_code: string;
  selected_products: VoucherPickerProduct[];
}

const CloseIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-[#999] hover:text-[#333]">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
);

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>
);

const ChevronDownIcon = ({ open = false }: { open?: boolean }) => (
  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className={`text-[#999] transition-transform ${open ? 'rotate-180' : ''}`}>
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>
);

const ChevronRightIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-[#999]">
    <polyline points="9 18 15 12 9 6"></polyline>
  </svg>
);

const PackageOpenIcon = () => (
  <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9.5 12 4l9 5.5-9 5.5L3 9.5Z"></path>
    <path d="M3 9.5V15l9 5 9-5V9.5"></path>
    <path d="M12 15v5"></path>
  </svg>
);

const CircleHelpIcon = () => (
  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-[#b0b0b0]">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.2-3 4"></path>
    <line x1="12" y1="17" x2="12.01" y2="17"></line>
  </svg>
);

const PlusIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"></line>
    <line x1="5" y1="12" x2="19" y2="12"></line>
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

export default function ProductVoucherCreateView({ runId, readOnly = false, detailCampaignId = null, onBackToVouchers }: ProductVoucherCreateViewProps) {
  const [voucherName, setVoucherName] = useState('');
  const [codePrefix] = useState('HOME');
  const [codeSuffix, setCodeSuffix] = useState('');
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
  
  // 代金券展示与适用商品相关状态
  const [displayType, setDisplayType] = useState<DisplayType>('all_pages');
  const [displayChannels, setDisplayChannels] = useState<string[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<VoucherPickerProduct[]>([]);
  
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTab, setPickerTab] = useState<ProductPickerTab>('select');
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState('');
  const [pickerKeyword, setPickerKeyword] = useState('');
  const [pickerKeywordInput, setPickerKeywordInput] = useState('');
  const [pickerCategory, setPickerCategory] = useState('all');
  const [pickerSearchField, setPickerSearchField] = useState<ProductPickerSearchField>('product_name');
  const [pickerAvailableOnly, setPickerAvailableOnly] = useState(true);
  const [pickerDropdownOpen, setPickerDropdownOpen] = useState<ProductPickerDropdown>(null);
  const [pickerCategoryParent, setPickerCategoryParent] = useState<ProductPickerCategoryParent>(null);
  const [pickerRows, setPickerRows] = useState<VoucherPickerProduct[]>([]);
  const [pickerSelections, setPickerSelections] = useState<Record<string, VoucherPickerProduct>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [currency, setCurrency] = useState('RM');
  const [codeChecking, setCodeChecking] = useState(false);
  const [codeCheck, setCodeCheck] = useState<VoucherCodeCheckResponse | null>(null);

  const effectiveReadOnly = readOnly || serverReadOnly;
  const pickerRowKey = (item: VoucherPickerProduct) => `${item.listing_id}-${item.variant_id ?? 0}`;
  const formatMoney = (value: number) => `RM ${Number(value || 0).toFixed(0)}`;
  const getProductPickerSearchFieldLabel = (value: ProductPickerSearchField) => value === 'product_id' ? '商品 ID' : '商品名称';

  const handleCodeSuffixChange = (value: string) => {
    setCodeSuffix(value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 5));
    setCodeCheck(null);
  };

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
      ? `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/detail/product_voucher/${detailCampaignId}`
      : `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/product-create/bootstrap`;
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
        if ('voucher_code' in result) {
          setCodeSuffix(result.voucher_code.startsWith(codePrefix) ? result.voucher_code.slice(codePrefix.length) : result.voucher_code);
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
        setDisplayType(result.form.display_type || 'all_pages');
        setDisplayChannels(result.form.display_channels || []);
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
  }, [runId, detailCampaignId, codePrefix]);

  useEffect(() => {
    const suffix = codeSuffix.trim().toUpperCase();
    if (detailCampaignId || !runId || !suffix || !/^[A-Z0-9]{1,5}$/.test(suffix)) {
      setCodeCheck(null);
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setCodeChecking(true);
      try {
        const params = new URLSearchParams({ voucher_type: 'product_voucher', code_suffix: suffix });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/code/check?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('code check failed');
        const result = (await response.json()) as VoucherCodeCheckResponse;
        if (!cancelled) setCodeCheck(result);
      } catch {
        if (!cancelled) setCodeCheck(null);
      } finally {
        if (!cancelled) setCodeChecking(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [codeSuffix, runId, detailCampaignId]);

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
          keyword: pickerKeyword.trim(),
          search_field: pickerSearchField,
          category_key: pickerCategory,
          page: '1',
          page_size: '20',
        });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/product-create/eligible-products?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('eligible products failed');
        const result = (await response.json()) as EligibleProductsResponse;
        if (cancelled) return;
        setPickerRows((result.items || []).map((item) => ({
          listing_id: item.listing_id,
          variant_id: item.variant_id,
          product_name: item.product_name,
          variant_name: item.variant_name || '',
          variant_ids: item.variant_ids || (item.variant_id ? [item.variant_id] : []),
          image_url: item.image_url,
          category_key: item.category_key || '未分类',
          category_label: item.category_label || '未分类',
          original_price: item.original_price,
          price_range_label: item.price_range_label,
          stock_available: item.stock_available,
          likes_count: item.likes_count,
          conflict: Boolean(item.conflict),
          conflict_reason: item.conflict_reason,
        })));
      } catch {
        if (!cancelled) setPickerError('可选商品加载失败，请稍后重试。');
      } finally {
        if (!cancelled) setPickerLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [pickerCategory, pickerKeyword, pickerOpen, pickerSearchField, pickerTab, runId]);

  const shopCategoryLeafOptions = useMemo(() => {
    const leafMap = new Map<string, string>();
    pickerRows.forEach((row) => {
      const category = row.category_label?.trim();
      if (category) leafMap.set(row.category_key || category, category);
    });
    return Array.from(leafMap.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'));
  }, [pickerRows]);

  const categoryOptions: ProductPickerCategoryOption[] = [
    { value: 'all', label: '全部分类', accent: true },
    { value: 'shopee', label: 'Shopee 分类', hasChild: true },
    { value: 'shop', label: '店铺分类', hasChild: true },
  ];

  const selectedCategoryLabel = useMemo(() => {
    if (pickerCategory === 'all') return '全部分类';
    const matchedShopCategory = shopCategoryLeafOptions.find((option) => option.value === pickerCategory);
    if (matchedShopCategory) return matchedShopCategory.label;
    return categoryOptions.find((option) => option.value === pickerCategory)?.label ?? '全部分类';
  }, [categoryOptions, pickerCategory, shopCategoryLeafOptions]);

  const searchFieldOptions: Array<{ value: ProductPickerSearchField; label: string }> = [
    { value: 'product_name', label: '商品名称' },
    { value: 'product_id', label: '商品 ID' },
  ];

  const pickerDisplayRows = useMemo(() => {
    const keyword = pickerKeyword.trim().toLowerCase();
    return pickerRows.filter((row) => {
      if (pickerCategory !== 'all' && row.category_key !== pickerCategory) return false;
      if (pickerAvailableOnly && (row.stock_available <= 0 || row.conflict)) return false;
      if (!keyword) return true;
      if (pickerSearchField === 'product_id') return String(row.listing_id).includes(keyword);
      return row.product_name.toLowerCase().includes(keyword);
    });
  }, [pickerAvailableOnly, pickerCategory, pickerKeyword, pickerRows, pickerSearchField]);

  const selectablePickerRows = useMemo(
    () => pickerDisplayRows.filter((row) => row.stock_available > 0 && !row.conflict),
    [pickerDisplayRows],
  );

  const allPickerRowsChecked = selectablePickerRows.length > 0 && selectablePickerRows.every((row) => Boolean(pickerSelections[pickerRowKey(row)]));

  const handleOpenPicker = () => {
    if (effectiveReadOnly) return;
    setPickerSelections({});
    setPickerTab('select');
    setPickerCategory('all');
    setPickerSearchField('product_name');
    setPickerAvailableOnly(true);
    setPickerDropdownOpen(null);
    setPickerCategoryParent(null);
    setPickerKeyword('');
    setPickerKeywordInput('');
    setPickerOpen(true);
  };

  const handleTogglePickerRow = (row: VoucherPickerProduct) => {
    const key = pickerRowKey(row);
    setPickerSelections((prev) => {
      if (prev[key]) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: row };
    });
  };

  const handleApplyPicker = () => {
    const pickedRows = Object.values(pickerSelections);
    if (!pickedRows.length) {
      setPickerOpen(false);
      return;
    }
    setSelectedProducts((prev) => {
      const existing = new Set(prev.map((item) => pickerRowKey(item)));
      const merged = [...prev];
      pickedRows.forEach((row) => {
        const key = pickerRowKey(row);
        if (!existing.has(key)) {
          existing.add(key);
          merged.push(row);
        }
      });
      return merged;
    });
    setPickerOpen(false);
  };

  const handleSearchPicker = () => {
    setPickerDropdownOpen(null);
    setPickerKeyword(pickerKeywordInput.trim());
  };

  const handleResetPicker = () => {
    setPickerCategory('all');
    setPickerSearchField('product_name');
    setPickerAvailableOnly(true);
    setPickerDropdownOpen(null);
    setPickerCategoryParent(null);
    setPickerKeywordInput('');
    setPickerKeyword('');
  };

  const handleRemoveSelectedProduct = (target: VoucherPickerProduct) => {
    setSelectedProducts((prev) => prev.filter((item) => pickerRowKey(item) !== pickerRowKey(target)));
  };

  const handleToggleAllPickerRows = () => {
    if (!selectablePickerRows.length) return;
    setPickerSelections((prev) => {
      const next = { ...prev };
      if (allPickerRowsChecked) {
        selectablePickerRows.forEach((row) => {
          delete next[pickerRowKey(row)];
        });
        return next;
      }
      selectablePickerRows.forEach((row) => {
        next[pickerRowKey(row)] = row;
      });
      return next;
    });
  };

  const validateForm = () => {
    if (!voucherName.trim()) return '请输入代金券名称。';
    if (!/^[A-Z0-9]{1,5}$/.test(codeSuffix.trim().toUpperCase())) return '代金券代码后缀仅允许 A-Z、0-9，且最多 5 个字符。';
    if (codeCheck && !codeCheck.available) return codeCheck.message;
    if (!voucherStartAt || !voucherEndAt) return '请选择代金券使用期限。';
    if (voucherStartAt >= voucherEndAt) return '代金券结束时间必须晚于开始时间。';
    if (displayBeforeStart && (!displayStartAt || displayStartAt >= voucherStartAt)) return '提前展示时间必须早于代金券开始时间。';
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
    if (displayType === 'specific_channels' && !displayChannels.includes('checkout_page')) return '请选择特定展示渠道。';
    if (!selectedProducts.length) return '请至少选择一个适用商品。';
    if (selectedProducts.length > 100) return '最多选择 100 个适用商品。';
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
    if (!token) {
      setError('登录已失效，请重新登录。');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/product-campaigns`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voucher_type: 'product_voucher',
          voucher_name: voucherName.trim(),
          code_suffix: codeSuffix.trim().toUpperCase(),
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
          display_type: displayType,
          display_channels: displayType === 'specific_channels' ? displayChannels : [],
          selected_products: selectedProducts.flatMap((item) => {
            if (item.variant_ids?.length) {
              return item.variant_ids.map((variantId) => ({ listing_id: item.listing_id, variant_id: variantId }));
            }
            return [{ listing_id: item.listing_id, variant_id: item.variant_id }];
          }),
        }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        throw new Error(result?.detail || '创建失败，请检查后重试。');
      }
      onBackToVouchers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败，请检查后重试。');
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
        {error && (
          <div className="mb-4 border border-red-100 bg-red-50 px-4 py-2 text-[13px] text-red-600 shrink-0">
            {error}
          </div>
        )}
        {loading && (
          <div className="mb-4 border border-[#e5e5e5] bg-white px-4 py-2 text-[13px] text-[#666] shrink-0">
            正在加载创建页数据...
          </div>
        )}

        <div className="flex items-start gap-6 shrink-0 h-full">
          <div className="flex-1 min-w-[800px] flex flex-col relative">
            <div className="flex flex-col gap-4 pb-6">
              
              {/* === 基础信息 === */}
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">基础信息</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-2 text-right pr-6">代金券类型</div>
                  <div>
                    <div className="relative flex h-[40px] w-[180px] items-center justify-center rounded-sm border border-[#ee4d2d] bg-white text-[#ee4d2d] cursor-pointer">
                      <svg viewBox="0 0 21 21" className="mr-2 h-[20px] w-[20px]">
                        <path fillRule="evenodd" clipRule="evenodd" d="M13.625 4.375V5h-6.25v-.625a3.125 3.125 0 116.25 0zM3.621 5h2.504v-.625a4.375 4.375 0 118.75 0V5h2.503a1.25 1.25 0 011.245 1.138l1.128 12.5A1.25 1.25 0 0118.506 20H2.492a1.25 1.25 0 01-1.245-1.362l1.129-12.5A1.25 1.25 0 013.62 5zm7.911 8.75a.705.705 0 01.063.327.607.607 0 01-.26.514 1.11 1.11 0 01-.669.185c-.444 0-.766-.09-.963-.268a1.11 1.11 0 01-.294-.847H7.688c-.009.441.114.875.351 1.246.263.38.63.676 1.058.853.496.21 1.03.314 1.57.307.818 0 1.462-.178 1.932-.533a1.74 1.74 0 00.704-1.468c0-.779-.385-1.39-1.156-1.834a6.322 6.322 0 00-1.212-.508 3.812 3.812 0 01-1.032-.459.638.638 0 01-.294-.5.619.619 0 01.264-.513c.217-.15.477-.222.74-.205.26-.015.517.07.717.238a.864.864 0 01.27.677h1.712a2.034 2.034 0 00-.338-1.156 2.165 2.165 0 00-.949-.782 3.295 3.295 0 00-1.373-.273 3.801 3.801 0 00-1.42.253c-.385.14-.723.384-.978.704a1.68 1.68 0 00-.342 1.043c0 .793.461 1.415 1.384 1.867.355.17.72.316 1.095.437.333.094.649.24.935.434.089.07.16.16.206.262z" fill="#EE4D2D" />
                      </svg>
                      商品代金券
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

                  <div className="pt-2 text-right pr-6">代金券代码</div>
                  <div className="max-w-[700px]">
                    <div className="flex h-9 w-[400px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                      <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#666]">{codePrefix}</div>
                      <input type="text" value={codeSuffix} onChange={(e) => handleCodeSuffixChange(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" placeholder="输入" />
                      <span className="text-[12px] text-[#999] pr-3">{codeSuffix.length}/5</span>
                    </div>
                    <div className="mt-2 text-[12px] leading-relaxed text-[#999]">
                      请输入 A-Z, 0-9; 最多 5 个字符。<br />
                      您的完整代金券代码为: {codePrefix}{codeSuffix}
                      {codeChecking ? <span className="ml-2 text-[#999]">校验中...</span> : codeCheck ? <span className={codeCheck.available ? 'ml-2 text-emerald-600' : 'ml-2 text-red-500'}>{codeCheck.message}</span> : null}
                    </div>
                  </div>

                  <div className="pt-2 text-right pr-6">代金券使用期限</div>
                  <div className="max-w-[700px]">
                    <div className="flex items-center gap-3">
                      <DateTimePicker value={voucherStartAt} onChange={effectiveReadOnly ? () => undefined : setVoucherStartAt} inputWidthClassName="w-[180px]" popupPlacement="bottom" maxValue={voucherEndAt || undefined} />
                      <span className="w-[18px] text-center text-[14px] text-[#999]">至</span>
                      <DateTimePicker value={voucherEndAt} onChange={effectiveReadOnly ? () => undefined : setVoucherEndAt} inputWidthClassName="w-[180px]" popupPlacement="bottom" minValue={voucherStartAt || undefined} />
                    </div>
                    <div className="mt-2 text-[12px] text-[#999]">这里显示和提交的时间均为当前对局的游戏时间。</div>
                    {displayBeforeStart ? (
                      <div className="mt-4 max-w-[400px]">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input type="checkbox" checked={displayBeforeStart} onChange={(e) => handleDisplayBeforeStartChange(e.target.checked)} disabled={effectiveReadOnly} className="h-[14px] w-[14px] accent-[#ee4d2d]" />
                          <span className="text-[14px] text-[#333]">提前展示代金券</span>
                        </label>
                        <div className="mt-3 ml-6">
                          <DateTimePicker value={displayStartAt} onChange={effectiveReadOnly ? () => undefined : setDisplayStartAt} inputWidthClassName="w-full" popupPlacement="bottom" maxValue={voucherStartAt || undefined} />
                          <div className="mt-2 text-[12px] text-[#999] leading-relaxed">代金券开始展示后，此部分将无法再次编辑。</div>
                        </div>
                      </div>
                    ) : (
                      <label className="mt-4 flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={displayBeforeStart} onChange={(e) => handleDisplayBeforeStartChange(e.target.checked)} disabled={effectiveReadOnly} className="h-[14px] w-[14px] accent-[#ee4d2d]" />
                        <span className="text-[14px] text-[#333]">提前展示代金券</span>
                      </label>
                    )}
                  </div>
                </div>
              </section>

              {/* === 奖励设置 === */}
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">奖励设置</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-1 text-right pr-6">奖励类型</div>
                  <div className="flex items-center gap-6">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="productVoucherRewardType" checked readOnly className="h-4 w-4 accent-[#ee4d2d]" />
                      <span>折扣</span>
                    </label>
                  </div>

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

                  {discountType === 'percent' && (
                    <>
                      <div className="pt-2 text-right pr-6">最大折扣金额</div>
                      <div className="max-w-[700px] flex flex-col gap-3">
                        <div className="flex items-center gap-6 mt-2">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input type="radio" name="maxDiscount" checked={maxDiscountType === 'set_amount'} onChange={() => setMaxDiscountType('set_amount')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                            <span>设置金额</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input type="radio" name="maxDiscount" checked={maxDiscountType === 'no_limit'} onChange={() => setMaxDiscountType('no_limit')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                            <span>无限制</span>
                          </label>
                        </div>
                        {maxDiscountType === 'set_amount' && (
                          <div className="flex h-9 w-[452px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                            <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>
                            <input type="number" value={maxDiscountAmount} onChange={(e) => setMaxDiscountAmount(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" />
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  <div className="pt-2 text-right pr-6">最低消费金额</div>
                  <div className="max-w-[700px]">
                    <div className="flex h-9 w-[452px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                      <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>
                      <input type="number" value={minSpendAmount} onChange={(e) => setMinSpendAmount(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" />
                    </div>
                  </div>

                  <div className="pt-2 text-right pr-6">使用数量</div>
                  <div className="max-w-[700px]">
                    <input type="number" value={usageLimit} onChange={(e) => setUsageLimit(e.target.value)} disabled={effectiveReadOnly} className="h-9 w-[452px] rounded-sm border border-[#e5e5e5] px-3 text-[14px] outline-none focus:border-[#ee4d2d] disabled:bg-white" />
                    <div className="mt-2 text-[12px] text-[#999]">所有买家可使用的代金券总数</div>
                  </div>

                  <div className="pt-2 text-right pr-6">每位买家最大发放量</div>
                  <div className="max-w-[700px]">
                    <input type="number" value={perBuyerLimit} onChange={(e) => setPerBuyerLimit(e.target.value)} disabled={effectiveReadOnly} className="h-9 w-[452px] rounded-sm border border-[#e5e5e5] px-3 text-[14px] outline-none focus:border-[#ee4d2d] disabled:bg-white" />
                  </div>
                </div>
              </section>

              {/* === 代金券展示与适用商品 === */}
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">代金券展示与适用商品</div>
                
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-8 text-[14px]">
                  
                  {/* 代金券展示设置 */}
                  <div className="pt-1 text-right pr-6">代金券展示设置</div>
                  <div className="flex flex-col gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="displayType" checked={displayType === 'all_pages'} onChange={() => setDisplayType('all_pages')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                      <span>在所有页面展示</span>
                      <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px]">?</span>
                    </label>
                    
                    <div>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input 
                          type="radio" 
                          name="displayType" 
                          checked={displayType === 'specific_channels'} 
                          onChange={() => {
                            setDisplayType('specific_channels');
                            setDisplayChannels(['checkout_page']); // 点选特定渠道时，自动勾选下方的复选框
                          }} 
                          disabled={effectiveReadOnly} 
                          className="h-4 w-4 accent-[#ee4d2d]" 
                        />
                        <span>特定渠道</span>
                      </label>
                      <div className="ml-6 mt-3 border border-[#e5e5e5] rounded-sm p-4 w-[240px] bg-[#fafafa]">
                        <label className="flex items-start gap-2 cursor-pointer">
                          <input type="checkbox" checked={displayChannels.includes('checkout_page')} onChange={(e) => setDisplayChannels(e.target.checked ? ['checkout_page'] : [])} disabled={effectiveReadOnly || displayType !== 'specific_channels'} className="h-4 w-4 mt-[2px] accent-[#ee4d2d]" />
                          <div className="flex flex-col">
                            <span>在订单支付页面展示</span>
                            <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px] mt-1">?</span>
                          </div>
                        </label>
                      </div>
                    </div>

                    <div>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="radio" name="displayType" checked={displayType === 'code_only'} onChange={() => setDisplayType('code_only')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                        <span>不展示</span>
                        <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px]">?</span>
                      </label>
                      <div className="mt-2 text-[12px] text-[#999]">代金券将不会展示在任何页面，但您可以通过代金券代码与用户分享。</div>
                    </div>
                  </div>

                  {/* 适用商品 */}
                  <div className="pt-1 text-right pr-6">适用商品</div>
                  <div className="max-w-[760px]">
                    
                    {/* 👇 1. 按钮与选中数量提示（已全中文并去除重复词） 👇 */}
                    {selectedProducts.length > 0 ? (
                      <div className="mb-3 flex items-center justify-between">
                        <div className="text-[14px] text-[#555]">
                          已选择 <span className="mx-1 font-medium text-[#333]">{selectedProducts.length}</span><span className="text-[#999]">件商品</span>
                        </div>
                        <button type="button" onClick={handleOpenPicker} disabled={effectiveReadOnly} className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-[#ee4d2d] px-4 text-[13px] text-[#ee4d2d] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">
                          <PlusIcon />
                          添加商品
                        </button>
                      </div>
                    ) : (
                      <div className="mb-3 flex items-center">
                        <button type="button" onClick={handleOpenPicker} disabled={effectiveReadOnly} className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-[#ee4d2d] px-4 text-[13px] text-[#ee4d2d] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">
                          <PlusIcon />
                          添加商品
                        </button>
                      </div>
                    )}

                    {/* 👇 2. 已选商品列表表格及表头（全中文翻译） 👇 */}
                    {selectedProducts.length > 0 ? (
                      <div className="overflow-hidden rounded-sm border border-[#e5e5e5] bg-white">
                        <div className="grid grid-cols-[1fr_130px_100px_80px] items-center bg-[#f5f5f5] px-4 py-3 text-[13px] text-[#666]">
                          <div>商品</div>
                          <div>原价</div>
                          <div className="flex items-center gap-1">库存 <CircleHelpIcon /></div>
                          <div className="text-center">操作</div>
                        </div>
                        <div className="max-h-[330px] overflow-y-auto px-4 custom-scrollbar">
                          {selectedProducts.map((item) => (
                            <div key={pickerRowKey(item)} className="grid grid-cols-[1fr_130px_100px_80px] items-center border-t border-[#f1f1f1] py-3 text-[14px] text-[#444] first:border-t-0">
                              <div className="flex min-w-0 items-center gap-3 pr-4">
                                <div className="h-10 w-10 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5]" style={item.image_url ? { backgroundImage: `url(${item.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined} />
                                <div className="min-w-0">
                                  <div className="truncate text-[#333]">{item.product_name}</div>
                                  <div className="mt-1 truncate text-[12px] text-[#8a8a8a]">ID: {item.listing_id}{item.variant_ids?.length ? ` · ${item.variant_ids.length} 个变体` : ''}</div>
                                </div>
                              </div>
                              <div className="text-[#555]">{item.price_range_label || formatMoney(item.original_price)}</div>
                              <div className="text-[#555]">{item.stock_available}</div>
                              <div className="flex justify-center">
                                <button type="button" onClick={() => handleRemoveSelectedProduct(item)} disabled={effectiveReadOnly} className="flex h-8 w-8 items-center justify-center rounded-full border border-[#e5e5e5] text-[#999] hover:border-[#ee4d2d] hover:text-[#ee4d2d] disabled:cursor-not-allowed disabled:opacity-50" aria-label="删除适用商品">
                                  <TrashIcon />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>

                </div>
              </section>
            </div>

            <div className="sticky bottom-0 z-50 mt-auto rounded-t-[4px] border-t border-l border-r border-[#ececec] bg-white px-8 py-3 shadow-[0_-4px_16px_rgba(0,0,0,0.04)]">
              <div className="flex items-center justify-end gap-4">
                <button type="button" onClick={onBackToVouchers} className="h-8 min-w-[80px] rounded-sm border border-[#e5e5e5] bg-white px-6 text-[14px] text-[#333] hover:bg-[#fafafa]">
                  取消
                </button>
                <button type="button" onClick={handleSubmit} disabled={effectiveReadOnly || loading || saving} className="h-8 min-w-[80px] rounded-sm bg-[#ee4d2d] px-6 text-[14px] text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899]">
                  {saving ? '提交中...' : '确认'}
                </button>
              </div>
            </div>
          </div>

          <div className="w-[320px] shrink-0 sticky top-0">
            <div className="border border-[#ececec] bg-white p-5 shadow-sm rounded-[2px]">
              <div className="text-[16px] font-medium text-[#333] mb-4">预览</div>
              <div
                className="mx-auto h-[310px] w-full bg-top bg-no-repeat bg-contain"
                style={{ backgroundImage: 'url("https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/mmf_portal_seller_root_dir/static/modules/vouchers-v2/image/multilang_voucher_illustration_th.b256577.png")' }}
              ></div>
              <div className="mt-4 text-[11px] text-[#999] text-center px-4">
                买家可以在选定商品上使用此代金券。
              </div>
            </div>
          </div>
        </div>
      </div>

      {pickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.32)]">
          <div className="flex h-[676px] w-[950px] flex-col border border-[#ececec] bg-white shadow-[0_18px_60px_rgba(15,23,42,0.22)]">
            <div className="flex items-center justify-between px-6 pb-2 pt-6">
              <div className="text-[18px] font-semibold text-[#2f2f2f]">选择商品</div>
              <button type="button" onClick={() => setPickerOpen(false)} className="text-[#888] hover:text-[#333]">
                <CloseIcon />
              </button>
            </div>
            <div className="border-b border-[#efefef] px-6">
              <div className="flex items-end gap-7 text-[14px]">
                <button type="button" onClick={() => setPickerTab('select')} className={`border-b-2 px-4 py-3 font-medium ${pickerTab === 'select' ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#666]'}`}>
                  选择商品
                </button>
                <button type="button" onClick={() => setPickerTab('upload')} className={`border-b-2 px-1 py-3 font-medium ${pickerTab === 'upload' ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#666]'}`}>
                  上传商品列表
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden px-6 py-4">
              {pickerTab === 'select' ? (
                <>
                  <div className="grid grid-cols-[72px_210px_64px_160px_1fr] items-center gap-3 text-[14px] text-[#555]">
                    <div>分类</div>
                    <div className="relative">
                      <button type="button" onClick={() => setPickerDropdownOpen((prev) => (prev === 'category' ? null : 'category'))} className={`flex h-10 w-full items-center justify-between border bg-white px-4 text-left text-[14px] ${pickerDropdownOpen === 'category' ? 'border-[#c8c8c8] shadow-[0_2px_10px_rgba(15,23,42,0.08)]' : 'border-[#d9d9d9]'} text-[#555]`}>
                        <span>{selectedCategoryLabel}</span>
                        <ChevronDownIcon open={pickerDropdownOpen === 'category'} />
                      </button>
                      {pickerDropdownOpen === 'category' ? (
                        <div className="absolute left-0 top-[44px] z-20 flex border border-[#e6e6e6] bg-white shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
                          <div className="w-[210px] py-1">
                            {categoryOptions.map((option) => (
                              <button key={option.value} type="button" onMouseEnter={() => setPickerCategoryParent(option.hasChild ? (option.value as ProductPickerCategoryParent) : null)} onClick={() => {
                                if (option.hasChild) {
                                  setPickerCategoryParent(option.value as ProductPickerCategoryParent);
                                  return;
                                }
                                setPickerCategory(option.value);
                                setPickerDropdownOpen(null);
                                setPickerCategoryParent(null);
                              }} className={`flex w-full items-center justify-between px-4 py-3 text-left text-[14px] hover:bg-[#fafafa] ${option.accent || pickerCategory === option.value ? 'text-[#ee4d2d]' : 'text-[#444]'}`}>
                                <span>{option.label}</span>
                                {option.hasChild ? <ChevronRightIcon /> : null}
                              </button>
                            ))}
                          </div>
                          {pickerCategoryParent === 'shop' ? (
                            <div className="w-[210px] border-l border-[#efefef] py-1">
                              {shopCategoryLeafOptions.length ? (
                                shopCategoryLeafOptions.map((option) => (
                                  <button key={option.value} type="button" onClick={() => {
                                    setPickerCategory(option.value);
                                    setPickerDropdownOpen(null);
                                    setPickerCategoryParent(null);
                                  }} className={`flex w-full items-center justify-between px-4 py-3 text-left text-[14px] hover:bg-[#fafafa] ${pickerCategory === option.value ? 'text-[#ee4d2d]' : 'text-[#444]'}`}>
                                    <span className="truncate">{option.label}</span>
                                  </button>
                                ))
                              ) : (
                                <div className="px-4 py-3 text-[13px] text-[#999]">当前店铺暂无可用分类</div>
                              )}
                            </div>
                          ) : null}
                          {pickerCategoryParent === 'shopee' ? (
                            <div className="w-[210px] border-l border-[#efefef] py-1">
                              <div className="px-4 py-3 text-[13px] leading-5 text-[#999]">Shopee 平台分类暂按店铺实际商品分类聚合展示。</div>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div className="pl-4">搜索</div>
                    <div className="relative">
                      <button type="button" onClick={() => setPickerDropdownOpen((prev) => (prev === 'search_field' ? null : 'search_field'))} className={`flex h-10 w-full items-center justify-between border bg-white px-4 text-left text-[14px] ${pickerDropdownOpen === 'search_field' ? 'border-[#c8c8c8] shadow-[0_2px_10px_rgba(15,23,42,0.08)]' : 'border-[#d9d9d9]'} text-[#555]`}>
                        <span>{getProductPickerSearchFieldLabel(pickerSearchField)}</span>
                        <ChevronDownIcon open={pickerDropdownOpen === 'search_field'} />
                      </button>
                      {pickerDropdownOpen === 'search_field' ? (
                        <div className="absolute left-0 top-[44px] z-20 w-full border border-[#e6e6e6] bg-white py-1 shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
                          {searchFieldOptions.map((option) => (
                            <button key={option.value} type="button" onClick={() => {
                              setPickerSearchField(option.value);
                              setPickerDropdownOpen(null);
                            }} className={`flex w-full items-center justify-between px-4 py-3 text-left text-[14px] hover:bg-[#fafafa] ${pickerSearchField === option.value ? 'text-[#ee4d2d]' : 'text-[#444]'}`}>
                              <span>{option.label}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex h-10 items-center border border-[#d9d9d9] bg-white px-3 focus-within:border-[#ee4d2d]">
                      <input value={pickerKeywordInput} onChange={(event) => setPickerKeywordInput(event.target.value)} onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          handleSearchPicker();
                        }
                      }} placeholder="请输入" className="w-full bg-transparent text-[14px] text-[#555] outline-none placeholder:text-[#b7b7b7]" />
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <button type="button" onClick={handleSearchPicker} className="h-8 bg-[#ee4d2d] px-4 text-[14px] font-medium text-white hover:bg-[#d83f21]">搜索</button>
                      <button type="button" onClick={handleResetPicker} className="h-8 border border-[#d9d9d9] bg-white px-4 text-[14px] text-[#555] hover:bg-[#fafafa]">重置</button>
                    </div>
                    <label className="flex items-center gap-2 text-[14px] text-[#555]">
                      <button type="button" onClick={() => setPickerAvailableOnly((prev) => !prev)} className={`flex h-4 w-4 items-center justify-center border ${pickerAvailableOnly ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#cfcfcf] bg-white'}`} aria-pressed={pickerAvailableOnly}>
                        {pickerAvailableOnly ? <CheckIcon /> : null}
                      </button>
                      仅显示可参与活动的商品
                    </label>
                  </div>

                  {pickerError ? <div className="mt-4 border border-red-100 bg-red-50 px-4 py-3 text-[13px] text-red-600">{pickerError}</div> : null}

                  <div className="mt-4 flex h-[388px] flex-col overflow-hidden border border-[#efefef]">
                    <div className="grid grid-cols-[50px_1.9fr_0.7fr_0.8fr_0.8fr] items-center bg-[#fafafa] px-4 py-3 text-[14px] text-[#666]">
                      <div>
                        <button type="button" onClick={handleToggleAllPickerRows} className={`flex h-[18px] w-[18px] items-center justify-center border ${allPickerRowsChecked ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#d9d9d9] bg-white'}`} aria-pressed={allPickerRowsChecked}>
                          {allPickerRowsChecked ? <CheckIcon /> : null}
                        </button>
                      </div>
                      <div>商品</div>
                      <div>销量</div>
                      <div>价格</div>
                      <div className="flex items-center gap-1">库存 <CircleHelpIcon /></div>
                    </div>

                    {pickerLoading ? (
                      <div className="space-y-3 p-4">
                        {Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-12 animate-pulse bg-[#f3f3f3]" />)}
                      </div>
                    ) : pickerDisplayRows.length ? (
                      <div className="flex-1 overflow-y-auto custom-scrollbar">
                        {pickerDisplayRows.map((row) => {
                          const key = pickerRowKey(row);
                          const checked = Boolean(pickerSelections[key]);
                          const disabledRow = Boolean(row.conflict) || row.stock_available <= 0;
                          return (
                            <div key={key} className="grid grid-cols-[50px_1.9fr_0.7fr_0.8fr_0.8fr] items-center border-t border-[#f1f1f1] px-4 py-3 text-[14px] text-[#444]">
                              <div>
                                <button type="button" onClick={() => {
                                  if (!disabledRow) handleTogglePickerRow(row);
                                }} className={`flex h-[18px] w-[18px] items-center justify-center border ${checked ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#d9d9d9] bg-white'} ${disabledRow ? 'cursor-not-allowed opacity-40' : ''}`} aria-pressed={checked} disabled={disabledRow}>
                                  {checked ? <CheckIcon /> : null}
                                </button>
                              </div>
                              <div className="flex min-w-0 items-center gap-3 pr-4">
                                <div className="h-10 w-10 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5]" style={row.image_url ? { backgroundImage: `url(${row.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined} />
                                <div className="min-w-0">
                                  <div className="truncate font-medium text-[#333]">{row.product_name}</div>
                                  <div className="mt-1 truncate text-[12px] text-[#8a8a8a]">ID: {row.listing_id}</div>
                                </div>
                              </div>
                              <div className="text-[#666]">{row.likes_count || '-'}</div>
                              <div className="text-[#555]">{row.price_range_label || formatMoney(row.original_price)}</div>
                              <div className={disabledRow ? 'text-[#d14343]' : 'text-[#555]'}>{row.conflict ? row.conflict_reason || '不可参与' : row.stock_available}</div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center text-[#9a9a9a]">
                        <div className="flex h-16 w-16 items-center justify-center border border-[#ededed] bg-[#fafafa] text-[#d6d6d6]"><PackageOpenIcon /></div>
                        <div className="text-[14px]">未找到符合条件的商品</div>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex h-full flex-col justify-between">
                  <div className="border border-dashed border-[#e5e5e5] bg-[#fcfcfc] px-8 py-12 text-center">
                    <div className="text-[16px] font-medium text-[#333]">上传商品列表</div>
                    <div className="mt-3 text-[14px] leading-6 text-[#8f8f8f]">
                      下一步这里会接入按模板上传商品名单的流程。
                      <br />
                      当前先保留与 Shopee 官方一致的弹窗入口结构。
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-[#efefef] px-6 py-4">
              <button type="button" onClick={() => setPickerOpen(false)} className="h-9 border border-[#d9d9d9] bg-white px-5 text-[14px] text-[#555] hover:bg-[#fafafa]">取消</button>
              <button type="button" onClick={handleApplyPicker} disabled={pickerTab !== 'select'} className="h-9 bg-[#ee4d2d] px-5 text-[14px] font-medium text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899]">确认</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
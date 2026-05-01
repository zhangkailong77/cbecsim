import { useCallback, useEffect, useMemo, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

// 图标组件集合
const CalendarIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
    <line x1="16" y1="2" x2="16" y2="6"></line>
    <line x1="8" y1="2" x2="8" y2="6"></line>
    <line x1="3" y1="10" x2="21" y2="10"></line>
  </svg>
);

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

// 日历切换箭头图标
const DoubleLeftIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" className="text-[#999] cursor-pointer hover:text-[#ee4d2d]"><polyline points="11 17 6 12 11 7"></polyline><polyline points="18 17 13 12 18 7"></polyline></svg>;
const LeftIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" className="text-[#999] cursor-pointer hover:text-[#ee4d2d]"><polyline points="15 18 9 12 15 6"></polyline></svg>;
const RightIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" className="text-[#999] cursor-pointer hover:text-[#ee4d2d]"><polyline points="9 18 15 12 9 6"></polyline></svg>;
const DoubleRightIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" className="text-[#999] cursor-pointer hover:text-[#ee4d2d]"><polyline points="13 17 18 12 13 7"></polyline><polyline points="6 17 11 12 6 7"></polyline></svg>;

function parseDateOnly(value: string): Date | null {
  if (!value) return null;
  const [year, month, day] = value.split('-').map((item) => Number(item));
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 0, 0, 0, 0);
}

function formatDateOnly(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function sameDate(left: Date, right: Date): boolean {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth() && left.getDate() === right.getDate();
}

function getMonthDayCells(viewDate: Date): Array<{ date: Date; inMonth: boolean }> {
  const viewYear = viewDate.getFullYear();
  const viewMonth = viewDate.getMonth();
  const monthStart = new Date(viewYear, viewMonth, 1);
  const monthStartWeekday = monthStart.getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate();
  return Array.from({ length: 42 }, (_, index) => {
    const dayNum = index - monthStartWeekday + 1;
    if (dayNum <= 0) return { date: new Date(viewYear, viewMonth - 1, daysInPrevMonth + dayNum), inMonth: false };
    if (dayNum > daysInMonth) return { date: new Date(viewYear, viewMonth + 1, dayNum - daysInMonth), inMonth: false };
    return { date: new Date(viewYear, viewMonth, dayNum), inMonth: true };
  });
}

interface ShopFlashSaleCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  onBackToFlashSale: () => void;
}

interface FlashSaleSlot {
  slot_key: string;
  display_time: string;
  cross_day: boolean;
  product_limit: number;
  available_product_count: number;
  selectable: boolean;
}

type ProductPickerTab = 'select' | 'upload';
type ProductPickerSearchField = 'product_name' | 'product_id';
type ProductPickerDropdown = 'category' | 'search_field' | null;
type ProductPickerCategoryParent = 'shopee' | 'shop' | null;

interface ProductPickerCategoryOption {
  value: string;
  label: string;
  accent?: boolean;
  hasChild?: boolean;
}

interface FlashSaleProduct {
  listing_id: number;
  variant_id: number | null;
  product_id?: number | null;
  product_name: string;
  variant_name: string;
  sku?: string | null;
  image_url?: string | null;
  category_key?: string;
  category_label?: string;
  original_price: number;
  price_range_label?: string | null;
  stock_available: number;
  likes_count?: number;
  suggested_flash_price: number | null;
  flash_price?: number | null;
  activity_stock_limit?: number | null;
  purchase_limit_per_buyer?: number | null;
  variations?: FlashSaleProduct[];
  enabled?: boolean;
  conflict?: boolean;
  conflict_reason?: string | null;
}

export default function ShopFlashSaleCreateView({ runId, readOnly = false, onBackToFlashSale }: ShopFlashSaleCreateViewProps) {
  const [activeCategory, setActiveCategory] = useState('母婴');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTimeSlot, setSelectedTimeSlot] = useState(''); 
  const [selectedSlotDate, setSelectedSlotDate] = useState('');
  const [currentGameDate, setCurrentGameDate] = useState('');
  const [calendarViewDate, setCalendarViewDate] = useState<Date | null>(null);
  const [slotRows, setSlotRows] = useState<FlashSaleSlot[]>([]);
  const [categoryRules, setCategoryRules] = useState<Record<string, { label: string; value: string }[]>>({});
  const [categoryKeyByLabel, setCategoryKeyByLabel] = useState<Record<string, string>>({});
  const [selectedProducts, setSelectedProducts] = useState<FlashSaleProduct[]>([]);
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
  const [pickerRows, setPickerRows] = useState<FlashSaleProduct[]>([]);
  const [pickerSelections, setPickerSelections] = useState<Record<string, FlashSaleProduct>>({});

  const groupedProducts = useMemo(() => {
    const groups: Record<number, { 
      listing_id: number; 
      product_name: string; 
      image_url: string; 
      purchase_limit_per_buyer: number | null;
      variations: FlashSaleProduct[] 
    }> = {};

    selectedProducts.forEach((p) => {
      if (!groups[p.listing_id]) {
        groups[p.listing_id] = {
          listing_id: p.listing_id,
          product_name: p.product_name,
          image_url: p.image_url || '',
          purchase_limit_per_buyer: p.purchase_limit_per_buyer ?? null,
          variations: [],
        };
      }
      groups[p.listing_id].variations.push(p);
    });

    return Object.values(groups);
  }, [selectedProducts]);

  const loadSlotRows = useCallback(async (date: string) => {
    if (!runId || !date) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    const slotResponse = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/slots?date=${date}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!slotResponse.ok) return;
    const slotResult = await slotResponse.json();
    setSlotRows(slotResult.slots || []);
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const loadBootstrap = async () => {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/create/bootstrap`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const result = await response.json();
      if (cancelled) return;
      const nextCategoryMap: Record<string, string> = {};
      const nextRuleMap: Record<string, { label: string; value: string }[]> = {};
      const categoryItems = result.categories || [];
      categoryItems.forEach((item: { key: string; label: string }) => {
        nextCategoryMap[item.label] = item.key;
        nextRuleMap[item.key] = result.category_rules?.[item.key] || [];
      });
      setCategoryKeyByLabel(nextCategoryMap);
      setCategoryRules(nextRuleMap);
      if (categoryItems.length > 0) setActiveCategory(categoryItems[0].label);
      
      setSelectedProducts(result.selected_products || []);
      
      const currentDate = String(result.meta?.current_game_time || result.meta?.current_tick || '').slice(0, 10);
      const parsedCurrentDate = parseDateOnly(currentDate);
      setCurrentGameDate(currentDate);
      setSelectedSlotDate(currentDate);
      if (parsedCurrentDate) setCalendarViewDate(parsedCurrentDate);
      await loadSlotRows(currentDate);
    };
    void loadBootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadSlotRows, runId]);

  useEffect(() => {
    if (!pickerOpen || pickerTab !== 'select' || !runId || !selectedSlotDate || !selectedTimeSlot) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPickerLoading(true);
      setPickerError('');
      try {
        const categoryKey = pickerCategory !== 'all' ? pickerCategory : categoryKeyByLabel[activeCategory] || 'all';
        const params = new URLSearchParams({
          slot_date: selectedSlotDate,
          slot_key: selectedTimeSlot,
          category_key: categoryKey,
          keyword: pickerKeyword.trim(),
          search_field: pickerSearchField,
          page: '1',
          page_size: '20',
        });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/eligible-products?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('eligible products failed');
        const result = await response.json();
        if (!cancelled) setPickerRows(result.items || []);
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
  }, [activeCategory, categoryKeyByLabel, pickerCategory, pickerKeyword, pickerOpen, pickerSearchField, pickerTab, runId, selectedSlotDate, selectedTimeSlot]);

  const categories = Object.keys(categoryKeyByLabel).length > 0 ? Object.keys(categoryKeyByLabel) : [
    '母婴', '工具与家装', '厨房用品', '收纳整理',
    '电视及配件', '美容护肤', '家具', '全部'
  ];

  const formatMoney = (value: number) => `RM ${Number(value || 0).toFixed(0)}`;
  const pickerRowKey = (item: FlashSaleProduct) => `${item.listing_id}-${item.variant_id ?? 0}`;
  const getProductPickerSearchFieldLabel = (value: ProductPickerSearchField) => value === 'product_id' ? '商品 ID' : '商品名称';
  const splitCategoryPath = (value: string) => value.split(/>|\/|›|»/).map((part) => part.trim()).filter(Boolean);

  const shopCategoryLeafOptions = useMemo(() => {
    const leafMap = new Map<string, string>();
    pickerRows.forEach((row) => {
      const categoryPath = row.category_label?.trim();
      if (!categoryPath) return;
      const parts = splitCategoryPath(categoryPath);
      leafMap.set(row.category_key || categoryPath, parts[parts.length - 1] || categoryPath);
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
    return pickerRows.filter((row) => {
      if (pickerCategory !== 'all' && row.category_key !== pickerCategory) return false;
      if (!pickerAvailableOnly) return true;
      return row.stock_available > 0 && !row.conflict;
    });
  }, [pickerAvailableOnly, pickerCategory, pickerRows]);

  const selectablePickerRows = useMemo(
    () => pickerDisplayRows.filter((row) => row.stock_available > 0 && !row.conflict),
    [pickerDisplayRows],
  );

  const allPickerRowsChecked = selectablePickerRows.length > 0 && selectablePickerRows.every((row) => Boolean(pickerSelections[pickerRowKey(row)]));

  const handleOpenPicker = () => {
    if (readOnly || !selectedTimeSlot) return;
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

  const handleTogglePickerRow = (row: FlashSaleProduct) => {
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

  const normalizeSelectedProduct = (item: FlashSaleProduct): FlashSaleProduct => ({
    ...item,
    flash_price: item.flash_price || item.suggested_flash_price || Math.max(0.01, Number((item.original_price * 0.9).toFixed(2))),
    activity_stock_limit: item.activity_stock_limit || Math.min(Math.max(item.stock_available, 5), 10000),
    purchase_limit_per_buyer: item.purchase_limit_per_buyer || null,
    enabled: item.enabled !== false,
  });

  const handleApplyPicker = () => {
    const pickedRows = Object.values(pickerSelections) as FlashSaleProduct[];
    if (!pickedRows.length) {
      setPickerOpen(false);
      return;
    }
    setSelectedProducts((prev) => {
      const existing = new Set(prev.map((item) => pickerRowKey(item)));
      const merged = [...prev];
      pickedRows.forEach((row) => {
        const items = row.variations?.length ? row.variations : [row];
        items.forEach((item) => {
          const key = pickerRowKey(item);
          if (!existing.has(key)) {
            existing.add(key);
            merged.push(normalizeSelectedProduct(item));
          }
        });
      });
      return merged;
    });
    setPickerOpen(false);
  };

  const handleUpdateSelectedProduct = (listingId: number, variantId: number | null, patch: Partial<FlashSaleProduct>) => {
    setSelectedProducts((prev) => prev.map((item) => (
      item.listing_id === listingId && item.variant_id === variantId ? { ...item, ...patch } : item
    )));
  };

  const handleToggleSelectedProduct = (listingId: number, variantId: number | null) => {
    setSelectedProducts((prev) => prev.map((item) => (
      item.listing_id === listingId && item.variant_id === variantId ? { ...item, enabled: item.enabled === false } : item
    )));
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

  const productCriteria = categoryRules[categoryKeyByLabel[activeCategory]] || [
    { label: '活动库存', value: '5 ~ 10000' },
    { label: '折扣限制', value: '5% ~ 99%' },
    { label: '商品评分(0.0-5.0)', value: '无限制' },
    { label: '点赞数', value: '无限制' },
    { label: '预购商品', value: '允许' },
    { label: '过去30天订单量', value: '无限制' },
    { label: '发货天数', value: '无限制' },
    { label: '重复控制', value: '无限制' },
  ];

  const timeSlots = slotRows.length > 0 ? slotRows.map((slot) => ({
    id: slot.slot_key,
    time: slot.display_time.replace(' +1', ''),
    products: `总可用 ${slot.available_product_count || slot.product_limit}`,
    isNextDay: slot.cross_day,
    selectable: slot.selectable,
  })) : [];

  const selectedDateObject = parseDateOnly(selectedSlotDate);
  const currentDateObject = parseDateOnly(currentGameDate);
  const calendarCells = calendarViewDate ? getMonthDayCells(calendarViewDate) : [];
  const calendarMonthLabel = calendarViewDate ? `${calendarViewDate.getFullYear()}年${calendarViewDate.getMonth() + 1}月` : '加载中';
  const selectedTimeSlotLabel = selectedTimeSlot ? timeSlots.find((slot) => slot.id === selectedTimeSlot)?.time : '';
  const selectedTimeSlotDisplay = selectedTimeSlot && selectedTimeSlotLabel ? `${selectedSlotDate} ${selectedTimeSlotLabel}` : '选择时间段';

  const shiftCalendarViewDate = (years: number, months: number) => {
    setCalendarViewDate((prev) => {
      if (!prev) return prev;
      return new Date(prev.getFullYear() + years, prev.getMonth() + months, 1);
    });
  };

  const handleSelectSlotDate = async (date: Date) => {
    if (readOnly || (currentDateObject && date.getTime() < currentDateObject.getTime())) return;
    const nextDate = formatDateOnly(date);
    setSelectedSlotDate(nextDate);
    setSelectedTimeSlot('');
    await loadSlotRows(nextDate);
  };

  const enabledProducts = selectedProducts.filter((item) => item.enabled !== false);

  const handleCreate = async () => {
    if (!runId || readOnly || !selectedSlotDate || !selectedTimeSlot || enabledProducts.length === 0) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    const items = selectedProducts.map((item) => ({
      listing_id: item.listing_id,
      variant_id: item.variant_id,
      flash_price: item.flash_price || item.suggested_flash_price || Math.max(0.01, Number((item.original_price * 0.9).toFixed(2))),
      activity_stock_limit: item.activity_stock_limit || Math.min(Math.max(item.stock_available, 5), 10000),
      purchase_limit_per_buyer: item.purchase_limit_per_buyer || 1,
      status: item.enabled === false ? 'disabled' : 'active',
    }));
    const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/campaigns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ campaign_name: '店铺限时抢购活动', slot_date: selectedSlotDate, slot_key: selectedTimeSlot, items }),
    });
    if (response.ok) onBackToFlashSale();
  };

  // 计算折扣百分比的小工具
  const calculateDiscountPercent = (original: number, flash: number) => {
    if (!original || !flash || original <= flash) return 0;
    return Math.round(((original - flash) / original) * 100);
  };

  // 定义统一的 Grid 布局列宽，确保表头和每张独立卡片完美对齐
  const tableGridCols = "grid-cols-[minmax(280px,2.5fr)_1fr_1.5fr_1fr_1.2fr_1fr_1fr_1fr] gap-x-2";

  return (
    <div className="flex-1 overflow-y-auto bg-[#f5f5f5] px-9 py-6 custom-scrollbar text-[#333] relative">
      <div className="mx-auto max-w-[1360px]">
        
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览创建页，但无法添加商品或正式提交。
          </div>
        )}

        {/* 1. 基础信息 Section */}
        <section className="bg-white px-8 py-7 shadow-sm border border-[#ebebeb] rounded-[2px]">
          <h2 className="text-[18px] font-medium text-[#333]">基础信息</h2>
          
          <div className="mt-8 grid grid-cols-[140px_1fr] items-start gap-y-8">
            <div className="pt-2 text-[14px] text-[#666] text-right pr-6">活动时间段</div>
            <div>
              <button
                onClick={() => !readOnly && setIsModalOpen(true)}
                disabled={readOnly}
                className="flex items-center gap-2 border border-[#ee4d2d] bg-white text-[#ee4d2d] px-4 py-2 rounded-sm text-[14px] hover:bg-[#fff6f4] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <CalendarIcon />
                {selectedTimeSlotDisplay}
              </button>
            </div>

            <div className="pt-3 text-[14px] text-[#666] text-right pr-6">商品条件</div>
            <div className="border border-[#ebebeb] rounded-sm p-6 max-w-[900px]">
              <div className="flex flex-wrap gap-3 mb-6">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`px-4 py-1.5 text-[14px] rounded-sm border ${
                      activeCategory === cat 
                        ? 'border-[#ee4d2d] text-[#ee4d2d]' 
                        : 'border-[#ebebeb] text-[#333] hover:border-[#ccc]'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div>
                <h3 className="text-[14px] font-medium text-[#333] mb-4">
                  {activeCategory} 商品条件
                </h3>
                <div className="grid grid-cols-2 gap-y-4 gap-x-8">
                  {productCriteria.map((item, index) => (
                    <div key={index} className="flex items-center text-[13px] text-[#666]">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#ee4d2d] mr-2 shrink-0"></div>
                      <span>{item.label}: {item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 2. 限时抢购商品 Section (核心修改区域) */}
        <section className="mt-5 bg-white px-8 py-7 shadow-sm border border-[#ebebeb] rounded-[2px]">
          <h2 className="text-[18px] font-medium text-[#333]">限时抢购商品</h2>
          
          {selectedProducts.length > 0 ? (
            <p className="mt-1 text-[13px] text-[#666]">
              您已为此限时抢购时间段启用 <span className="font-medium text-[#333]">{enabledProducts.length}</span> / 50 个商品。
            </p>
          ) : (
            <p className="mt-1 text-[13px] text-[#999]">添加活动商品前，请仔细查阅商品条件。</p>
          )}

          <div className="mt-5 mb-5 flex items-center justify-between">
            <button
              type="button"
              disabled={readOnly || !selectedTimeSlot}
              onClick={handleOpenPicker}
              className={`inline-flex h-9 items-center gap-1.5 border px-5 text-[14px] rounded-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                selectedProducts.length > 0 
                  ? 'border-[#d9d9d9] bg-white text-[#555] hover:bg-[#fafafa]' 
                  : 'border-[#ff9d8c] bg-white text-[#ff735c] hover:bg-[#fff6f4]'
              }`}
            >
              <PlusIcon />
              添加商品 {selectedProducts.length > 0 ? `(${selectedProducts.length})` : ''}
            </button>
          </div>

          {/* ---------------- 核心变体配置列表 ---------------- */}
          {groupedProducts.length > 0 && (
            <div>
              
              {/* 分离的表头 (Independent Header) */}
              <div className={`grid ${tableGridCols} bg-[#fafafa] border border-[#ebebeb] rounded-sm px-5 py-3.5 text-[13px] text-[#666] font-medium`}>
                <div>商品变体</div>
                <div>原价</div>
                <div>折后价</div>
                <div>折扣</div>
                <div className="flex items-center gap-1">活动库存 </div>
                <div className="flex items-center gap-1">现有库存 </div>
                <div className="flex items-center gap-1">订单限购 </div>
                <div className="text-center">启用 / 停用</div>
              </div>

              {/* 独立的商品卡片列表 (Independent Product Cards) */}
              {groupedProducts.map((group) => (
                <div key={group.listing_id} className="mt-3 border border-[#ebebeb] rounded-sm bg-white">
                  
                  {/* 主商品行 (Parent Row) */}
                  <div className={`grid ${tableGridCols} items-center px-5 py-4 border-b border-[#ebebeb]`}>
                    {/* 第一列：商品图片和名称 */}
                    <div className="flex items-center gap-3">
                      <div 
                        className="w-12 h-12 bg-[#f5f5f5] border border-[#ebebeb] flex-shrink-0"
                        style={group.image_url ? { backgroundImage: `url(${group.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}
                      ></div>
                      <div className="text-[14px] text-[#333] font-medium truncate">
                        {group.product_name}
                      </div>
                    </div>
                    {/* 中间 5 列全部留白占位，保证第七列对其 */}
                    <div></div><div></div><div></div><div></div><div></div>
                    
                    {/* 第七列：统一订单限购 */}
                    <div className="text-[13px] text-[#666]">
                      {group.purchase_limit_per_buyer ? group.purchase_limit_per_buyer : '无限制'}
                    </div>
                    {/* 第八列：留白 */}
                    <div></div>
                  </div>

                  {/* 变体行列表 (Child Rows) */}
                  <div className="px-5 py-2">
                    {group.variations.map((variant) => {
                      const discountPct = calculateDiscountPercent(variant.original_price, variant.flash_price || variant.original_price);
                      
                      return (
                        <div key={variant.variant_id || variant.listing_id} className={`grid ${tableGridCols} items-center py-3 text-[13px]`}>
                          {/* 变体名称 */}
                          <div className="pl-[60px] pr-4 text-[#555] truncate">
                            {variant.variant_name || '默认款式'}
                          </div>
                          
                          {/* 原价 */}
                          <div className="text-[#666]">{formatMoney(variant.original_price)}</div>
                          
                          {/* 折后价 (带灰色 RM 前缀的输入框) */}
                          <div className="pr-4">
                            <div className="flex items-center h-[34px] border border-[#d9d9d9] rounded-[2px] overflow-hidden focus-within:border-[#ee4d2d] bg-white">
                              <span className="text-[#999] bg-[#fafafa] px-2 h-full flex items-center border-r border-[#d9d9d9]">RM</span>
                              <input
                                type="text"
                                disabled={readOnly}
                                value={variant.flash_price ?? ''}
                                onChange={(event) => {
                                  const rawValue = event.target.value.trim();
                                  const nextValue = Number(rawValue);
                                  handleUpdateSelectedProduct(variant.listing_id, variant.variant_id, {
                                    flash_price: rawValue && Number.isFinite(nextValue) ? nextValue : null,
                                  });
                                }}
                                className="w-full text-[#333] outline-none px-2 bg-transparent"
                              />
                            </div>
                          </div>
                          
                          {/* 折扣标签 */}
                          <div>
                            {discountPct > 0 ? (
                              <span className="inline-block px-1.5 py-0.5 border border-[#ff8b73] text-[#ee4d2d] bg-[#fff6f4] text-[12px] font-medium leading-none rounded-sm">
                                {discountPct}%OFF
                              </span>
                            ) : '-'}
                          </div>
                          
                          {/* 活动库存 (输入框形态) */}
                          <div className="pr-4">
                            <div className="flex items-center h-[34px] border border-[#d9d9d9] rounded-[2px] px-2 focus-within:border-[#ee4d2d] bg-white">
                              <input
                                type="text"
                                disabled={readOnly}
                                value={variant.activity_stock_limit ?? ''}
                                onChange={(event) => {
                                  const rawValue = event.target.value.trim();
                                  const nextValue = Number(rawValue);
                                  handleUpdateSelectedProduct(variant.listing_id, variant.variant_id, {
                                    activity_stock_limit: rawValue && Number.isFinite(nextValue) ? nextValue : null,
                                  });
                                }}
                                className="w-full text-[#333] outline-none bg-transparent"
                              />
                            </div>
                          </div>
                          
                          {/* 现有库存 */}
                          <div className="text-[#333]">{variant.stock_available}</div>
                          
                          {/* 订单限购留白 */}
                          <div></div>
                          
                          {/* 启用/停用 绿色 Toggle */}
                          <div className="flex justify-center">
                            <button
                              type="button"
                              disabled={readOnly}
                              onClick={() => handleToggleSelectedProduct(variant.listing_id, variant.variant_id)}
                              className={`w-10 h-5 rounded-full relative cursor-pointer transition-colors disabled:cursor-not-allowed ${variant.enabled === false ? 'bg-[#d9d9d9]' : 'bg-[#26b562]'}`}
                            >
                              <div className={`w-4 h-4 bg-white rounded-full absolute top-0.5 shadow-sm transition-all ${variant.enabled === false ? 'left-0.5' : 'right-0.5'}`}></div>
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {/* 商品卡片底部 Footer */}
                  <div className="bg-[#fafafa] border-t border-[#ebebeb] px-5 py-3.5 flex items-center justify-between rounded-b-sm">
                    <div className="text-[13px] text-[#05a] cursor-pointer hover:underline">
                      {group.variations.filter((variant) => variant.enabled === false).length} 个已停用变体
                    </div>
                    <div className="text-[13px] text-[#666]">
                      共 {group.variations.length} 个变体
                    </div>
                  </div>

                </div>
              ))}

            </div>
          )}
          {/* ---------------- 变体配置列表结束 ---------------- */}

        </section>

        {/* 底部操作按钮 */}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button type="button" onClick={onBackToFlashSale} className="h-9 border border-[#d9d9d9] bg-white px-6 text-[14px] text-[#333] rounded-sm hover:bg-[#fafafa]">
            取消
          </button>
          <button type="button" onClick={handleCreate} disabled={readOnly || !selectedTimeSlot || enabledProducts.length === 0} className={`h-9 px-6 text-[14px] text-white rounded-sm ${enabledProducts.length > 0 ? 'bg-[#ee4d2d] hover:bg-[#d83f21]' : 'bg-[#f3a899] cursor-not-allowed'}`}>
            确认
          </button>
        </div>

      </div>

      {/* --- 弹窗 Modal 区域 (保持不变) --- */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-sm shadow-xl w-[860px] flex flex-col overflow-hidden">
            
            {/* 弹窗 Header */}
            <div className="px-6 py-4 flex items-center justify-between border-b border-[#ebebeb]">
              <h2 className="text-[18px] font-medium text-[#333]">选择店铺限时抢购时间段</h2>
              <button onClick={() => setIsModalOpen(false)} className="outline-none">
                <CloseIcon />
              </button>
            </div>

            {/* 弹窗 Body (分左右两列) */}
            <div className="flex h-[420px]">
              
              {/* 左侧：日期选择 */}
              <div className="flex-1 border-r border-[#ebebeb] p-6 flex flex-col">
                <h3 className="text-[14px] text-[#333] mb-4">日期</h3>
                
                {/* 模拟日历 */}
                <div className="flex-1 select-none">
                  {/* 日历头部：年月切换 */}
                  <div className="flex items-center justify-between mb-4 px-2">
                    <div className="flex gap-2">
                      <button type="button" onClick={() => shiftCalendarViewDate(-1, 0)} className="leading-none"><DoubleLeftIcon /></button>
                      <button type="button" onClick={() => shiftCalendarViewDate(0, -1)} className="leading-none"><LeftIcon /></button>
                    </div>
                    <div className="text-[14px] font-medium text-[#333]">{calendarMonthLabel}</div>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => shiftCalendarViewDate(0, 1)} className="leading-none"><RightIcon /></button>
                      <button type="button" onClick={() => shiftCalendarViewDate(1, 0)} className="leading-none"><DoubleRightIcon /></button>
                    </div>
                  </div>

                  {/* 星期表头 */}
                  <div className="grid grid-cols-7 text-center text-[13px] text-[#999] mb-3">
                    <div>日</div><div>一</div><div>二</div><div>三</div><div>四</div><div>五</div><div>六</div>
                  </div>

                  <div className="grid grid-cols-7 text-center text-[13px]">
                    {calendarCells.map((cell) => {
                      const disabled = !cell.inMonth || (currentDateObject !== null && cell.date.getTime() < currentDateObject.getTime());
                      const selected = selectedDateObject !== null && sameDate(cell.date, selectedDateObject);
                      const slotCount = selected ? timeSlots.length : 4;
                      return (
                        <div key={formatDateOnly(cell.date)} className="py-1">
                          <button
                            type="button"
                            disabled={disabled}
                            onClick={() => void handleSelectSlotDate(cell.date)}
                            className={`w-full rounded-sm py-1 mx-1 ${
                              selected
                                ? 'bg-[#ee4d2d] text-white cursor-pointer'
                                : disabled
                                  ? 'text-[#ccc] cursor-default'
                                  : 'text-[#ee4d2d] hover:bg-[#fff6f4] cursor-pointer'
                            }`}
                          >
                            <div className="font-medium">{cell.date.getDate()}</div>
                            {!disabled && <div className="text-[10px] transform scale-90 leading-tight">{slotCount}个时间段</div>}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* 右侧：时间段列表 */}
              <div className="flex-1 p-6 flex flex-col bg-white">
                <h3 className="text-[14px] text-[#333] mb-4">时间段</h3>
                
                {/* 列表表头 */}
                <div className="grid grid-cols-[1.5fr_1fr] bg-[#fafafa] border border-[#ebebeb] px-4 py-2.5 text-[13px] text-[#666]">
                  <div>时间段</div>
                  <div>商品</div>
                </div>
                
                {/* 列表主体 */}
                <div className="border-x border-b border-[#ebebeb] flex-1 overflow-y-auto">
                  {timeSlots.map((slot) => (
                    <label 
                      key={slot.id} 
                      className={`grid grid-cols-[1.5fr_1fr] px-4 py-3 border-b border-[#ebebeb] last:border-0 items-center cursor-pointer hover:bg-[#fafafa] transition-colors ${selectedTimeSlot === slot.id ? 'bg-[#fff6f4]' : ''}`}
                      onClick={() => setSelectedTimeSlot(slot.id)}
                    >
                      <div className="flex items-center gap-3 text-[13px] text-[#333]">
                        {/* 自定义单选框样式 */}
                        <div className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${selectedTimeSlot === slot.id ? 'border-[#ee4d2d]' : 'border-[#d9d9d9]'}`}>
                          {selectedTimeSlot === slot.id && <div className="w-2 h-2 rounded-full bg-[#ee4d2d]"></div>}
                        </div>
                        <span>
                          {slot.time}
                          {slot.isNextDay && <sup className="text-[#999] ml-1 text-[10px]">+1</sup>}
                        </span>
                      </div>
                      <div className="text-[13px] text-[#666]">
                        {slot.products}
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* 弹窗 Footer */}
            <div className="px-6 py-4 flex items-center justify-end gap-3 border-t border-[#ebebeb]">
              <button 
                onClick={() => setIsModalOpen(false)}
                className="h-8 border border-[#d9d9d9] bg-white px-5 text-[14px] text-[#333] rounded-sm hover:bg-[#fafafa]"
              >
                取消
              </button>
              <button 
                onClick={() => setIsModalOpen(false)}
                disabled={!selectedTimeSlot}
                className="h-8 bg-[#ee4d2d] px-5 text-[14px] text-white rounded-sm hover:bg-[#d83f21] disabled:bg-[#f3a899] disabled:cursor-not-allowed"
              >
                确认
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 选择商品 Picker Modal 区域 (保持不变) */}
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
                <button
                  type="button"
                  onClick={() => setPickerTab('select')}
                  className={`border-b-2 px-4 py-3 font-medium ${
                    pickerTab === 'select' ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#666]'
                  }`}
                >
                  选择商品
                </button>
                <button
                  type="button"
                  onClick={() => setPickerTab('upload')}
                  className={`border-b-2 px-1 py-3 font-medium ${
                    pickerTab === 'upload' ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#666]'
                  }`}
                >
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
                      <button
                        type="button"
                        onClick={() => setPickerDropdownOpen((prev) => (prev === 'category' ? null : 'category'))}
                        className={`flex h-10 w-full items-center justify-between border bg-white px-4 text-left text-[14px] ${
                          pickerDropdownOpen === 'category' ? 'border-[#c8c8c8] shadow-[0_2px_10px_rgba(15,23,42,0.08)]' : 'border-[#d9d9d9]'
                        } text-[#555]`}
                      >
                        <span>{selectedCategoryLabel}</span>
                        <ChevronDownIcon open={pickerDropdownOpen === 'category'} />
                      </button>
                      {pickerDropdownOpen === 'category' ? (
                        <div className="absolute left-0 top-[44px] z-20 flex border border-[#e6e6e6] bg-white shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
                          <div className="w-[210px] py-1">
                            {categoryOptions.map((option) => (
                              <button
                                key={option.value}
                                type="button"
                                onMouseEnter={() => setPickerCategoryParent(option.hasChild ? (option.value as ProductPickerCategoryParent) : null)}
                                onClick={() => {
                                  if (option.hasChild) {
                                    setPickerCategoryParent(option.value as ProductPickerCategoryParent);
                                    return;
                                  }
                                  setPickerCategory(option.value);
                                  setPickerDropdownOpen(null);
                                  setPickerCategoryParent(null);
                                }}
                                className={`flex w-full items-center justify-between px-4 py-3 text-left text-[14px] hover:bg-[#fafafa] ${
                                  option.accent || pickerCategory === option.value ? 'text-[#ee4d2d]' : 'text-[#444]'
                                }`}
                              >
                                <span>{option.label}</span>
                                {option.hasChild ? <ChevronRightIcon /> : null}
                              </button>
                            ))}
                          </div>
                          {pickerCategoryParent === 'shop' ? (
                            <div className="w-[210px] border-l border-[#efefef] py-1">
                              {shopCategoryLeafOptions.length ? (
                                shopCategoryLeafOptions.map((option) => (
                                  <button
                                    key={option.value}
                                    type="button"
                                    onClick={() => {
                                      setPickerCategory(option.value);
                                      setPickerDropdownOpen(null);
                                      setPickerCategoryParent(null);
                                    }}
                                    className={`flex w-full items-center justify-between px-4 py-3 text-left text-[14px] hover:bg-[#fafafa] ${
                                      pickerCategory === option.value ? 'text-[#ee4d2d]' : 'text-[#444]'
                                    }`}
                                  >
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
                      <button
                        type="button"
                        onClick={() => setPickerDropdownOpen((prev) => (prev === 'search_field' ? null : 'search_field'))}
                        className={`flex h-10 w-full items-center justify-between border bg-white px-4 text-left text-[14px] ${
                          pickerDropdownOpen === 'search_field' ? 'border-[#c8c8c8] shadow-[0_2px_10px_rgba(15,23,42,0.08)]' : 'border-[#d9d9d9]'
                        } text-[#555]`}
                      >
                        <span>{getProductPickerSearchFieldLabel(pickerSearchField)}</span>
                        <ChevronDownIcon open={pickerDropdownOpen === 'search_field'} />
                      </button>
                      {pickerDropdownOpen === 'search_field' ? (
                        <div className="absolute left-0 top-[44px] z-20 w-full border border-[#e6e6e6] bg-white py-1 shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
                          {searchFieldOptions.map((option) => (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => {
                                setPickerSearchField(option.value);
                                setPickerDropdownOpen(null);
                              }}
                              className={`flex w-full items-center justify-between px-4 py-3 text-left text-[14px] hover:bg-[#fafafa] ${
                                pickerSearchField === option.value ? 'text-[#ee4d2d]' : 'text-[#444]'
                              }`}
                            >
                              <span>{option.label}</span>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex h-10 items-center border border-[#d9d9d9] bg-white px-3 focus-within:border-[#ee4d2d]">
                      <input
                        value={pickerKeywordInput}
                        onChange={(event) => setPickerKeywordInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault();
                            handleSearchPicker();
                          }
                        }}
                        placeholder="请输入"
                        className="w-full bg-transparent text-[14px] text-[#555] outline-none placeholder:text-[#b7b7b7]"
                      />
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <button type="button" onClick={handleSearchPicker} className="h-8 bg-[#ee4d2d] px-4 text-[14px] font-medium text-white hover:bg-[#d83f21]">
                        搜索
                      </button>
                      <button type="button" onClick={handleResetPicker} className="h-8 border border-[#d9d9d9] bg-white px-4 text-[14px] text-[#555] hover:bg-[#fafafa]">
                        重置
                      </button>
                    </div>
                    <label className="flex items-center gap-2 text-[14px] text-[#555]">
                      <button
                        type="button"
                        onClick={() => setPickerAvailableOnly((prev) => !prev)}
                        className={`flex h-4 w-4 items-center justify-center border ${pickerAvailableOnly ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#cfcfcf] bg-white'}`}
                        aria-pressed={pickerAvailableOnly}
                      >
                        {pickerAvailableOnly ? <CheckIcon /> : null}
                      </button>
                      仅显示可参与活动的商品
                    </label>
                  </div>

                  {pickerError ? <div className="mt-4 border border-red-100 bg-red-50 px-4 py-3 text-[13px] text-red-600">{pickerError}</div> : null}

                  <div className="mt-4 flex h-[388px] flex-col overflow-hidden border border-[#efefef]">
                    <div className="grid grid-cols-[50px_1.9fr_0.7fr_0.8fr_0.8fr] items-center bg-[#fafafa] px-4 py-3 text-[14px] text-[#666]">
                      <div>
                        <button
                          type="button"
                          onClick={handleToggleAllPickerRows}
                          className={`flex h-[18px] w-[18px] items-center justify-center border ${allPickerRowsChecked ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#d9d9d9] bg-white'}`}
                          aria-pressed={allPickerRowsChecked}
                        >
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
                        {Array.from({ length: 5 }).map((_, index) => (
                          <div key={index} className="h-12 animate-pulse bg-[#f3f3f3]" />
                        ))}
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
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (!disabledRow) handleTogglePickerRow(row);
                                  }}
                                  className={`flex h-[18px] w-[18px] items-center justify-center border ${checked ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#d9d9d9] bg-white'} ${disabledRow ? 'cursor-not-allowed opacity-40' : ''}`}
                                  aria-pressed={checked}
                                  disabled={disabledRow}
                                >
                                  {checked ? <CheckIcon /> : null}
                                </button>
                              </div>
                              <div className="flex min-w-0 items-center gap-3 pr-4">
                                <div
                                  className="h-10 w-10 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5]"
                                  style={row.image_url ? { backgroundImage: `url(${row.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}
                                />
                                <div className="min-w-0">
                                  <div className="truncate font-medium text-[#333]">{row.product_name}</div>
                                  <div className="mt-1 truncate text-[12px] text-[#8a8a8a]">
                                    ID: {row.listing_id}
                                  </div>
                                </div>
                              </div>
                              <div className="text-[#666]">{row.likes_count || '-'}</div>
                              <div className="text-[#555]">{row.price_range_label || formatMoney(row.original_price)}</div>
                              <div className={disabledRow ? 'text-[#d14343]' : 'text-[#555]'}>
                                {row.conflict ? row.conflict_reason || '不可参与' : row.stock_available}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center text-[#9a9a9a]">
                        <div className="flex h-16 w-16 items-center justify-center border border-[#ededed] bg-[#fafafa] text-[#d6d6d6]">
                          <PackageOpenIcon />
                        </div>
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
              <button type="button" onClick={() => setPickerOpen(false)} className="h-9 border border-[#d9d9d9] bg-white px-5 text-[14px] text-[#555] hover:bg-[#fafafa]">
                取消
              </button>
              <button
                type="button"
                onClick={handleApplyPicker}
                disabled={pickerTab !== 'select'}
                className="h-9 bg-[#ee4d2d] px-5 text-[14px] font-medium text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899]"
              >
                确认
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
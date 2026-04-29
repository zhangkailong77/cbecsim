import { Check, Gift, ShoppingBag, Pencil, PackageOpen, X, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import DateTimePicker from '../components/DateTimePicker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type PromoType = 'discount' | 'gift';
type ApiPromotionType = 'add_on' | 'gift';

interface AddOnDealCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  onBackToDiscount: () => void;
}

interface AddOnProductRow {
  listing_id: number;
  variant_id: number | null;
  product_id: number | null;
  product_name: string;
  variant_name: string;
  image_url: string | null;
  sku: string | null;
  original_price: number;
  stock_available: number;
  addon_price: number | null;
  reward_qty: number;
  suggested_addon_price: number | null;
}

interface AddOnBootstrapResponse {
  form: {
    campaign_name: string;
    start_at: string | null;
    end_at: string | null;
    addon_purchase_limit: number | null;
    gift_min_spend: number | null;
  };
  selected_main_products?: AddOnProductRow[];
  selected_reward_products?: AddOnProductRow[];
  draft: { id: number } | null;
}

interface AddOnEligibleProductsResponse {
  items: AddOnProductRow[];
}

function toApiPromotionType(type: PromoType): ApiPromotionType {
  return type === 'gift' ? 'gift' : 'add_on';
}

function formatDateTimeText(value: string) {
  if (!value) return '-';
  const [datePart, timePart = ''] = value.split('T');
  const [year, month, day] = datePart.split('-');
  return `${day}-${month}-${year} ${timePart}`;
}

export default function AddOnDealCreateView({ runId, readOnly = false, onBackToDiscount }: AddOnDealCreateViewProps) {
  const [promoType, setPromoType] = useState<PromoType>('discount');
  const [isBasicInfoSaved, setIsBasicInfoSaved] = useState(false);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [campaignName, setCampaignName] = useState('');
  const [startAt, setStartAt] = useState('');
  const [endAt, setEndAt] = useState('');
  const [addonPurchaseLimit, setAddonPurchaseLimit] = useState('');
  const [giftMinSpend, setGiftMinSpend] = useState('');
  const [giftQty, setGiftQty] = useState('1');
  const [mainProducts, setMainProducts] = useState<AddOnProductRow[]>([]);
  const [rewardProducts, setRewardProducts] = useState<AddOnProductRow[]>([]);
  const [mainCandidates, setMainCandidates] = useState<AddOnProductRow[]>([]);
  const [rewardCandidates, setRewardCandidates] = useState<AddOnProductRow[]>([]);
  const [mainPickerOpen, setMainPickerOpen] = useState(false);
  const [rewardPickerOpen, setRewardPickerOpen] = useState(false);
  const [pickerSelections, setPickerSelections] = useState<Record<string, AddOnProductRow>>({});
  const [saving, setSaving] = useState(false);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    let cancelled = false;
    const loadBootstrap = async () => {
      setError('');
      try {
        const params = new URLSearchParams({ promotion_type: toApiPromotionType(promoType) });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/add-on/create/bootstrap?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('bootstrap failed');
        const result = (await response.json()) as AddOnBootstrapResponse;
        if (cancelled) return;
        setDraftId(result.draft?.id ?? null);
        setCampaignName(result.form.campaign_name || '');
        setStartAt(result.form.start_at || '');
        setEndAt(result.form.end_at || '');
        setAddonPurchaseLimit(result.form.addon_purchase_limit ? String(result.form.addon_purchase_limit) : '');
        setGiftMinSpend(result.form.gift_min_spend ? String(result.form.gift_min_spend) : '');
        setMainProducts(result.selected_main_products || []);
        setRewardProducts(result.selected_reward_products || []);
      } catch {
        if (!cancelled) setError('加价购创建页加载失败，请稍后重试。');
      }
    };
    void loadBootstrap();
    return () => {
      cancelled = true;
    };
  }, [promoType, runId]);

  const productKey = (product: AddOnProductRow) => `${product.listing_id}:${product.variant_id || 0}`;

  const fetchCandidates = async (role: 'main' | 'reward') => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    setLoadingProducts(true);
    setError('');
    try {
      const endpoint = role === 'main' ? 'eligible-main-products' : 'eligible-reward-products';
      const params = new URLSearchParams({ promotion_type: toApiPromotionType(promoType), page: '1', page_size: '20' });
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/add-on/${endpoint}?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('load products failed');
      const result = (await response.json()) as AddOnEligibleProductsResponse;
      if (role === 'main') setMainCandidates(result.items || []);
      else setRewardCandidates(result.items || []);
    } catch {
      setError('商品列表加载失败，请稍后重试。');
    } finally {
      setLoadingProducts(false);
    }
  };

  const handleOpenMainPicker = () => {
    const initialSelections: Record<string, AddOnProductRow> = {};
    mainProducts.forEach((product) => {
      initialSelections[productKey(product)] = product;
    });
    setPickerSelections(initialSelections);
    setMainPickerOpen(true);
    setRewardPickerOpen(false);
    void fetchCandidates('main');
  };

  const handleOpenRewardPicker = () => {
    const initialSelections: Record<string, AddOnProductRow> = {};
    rewardProducts.forEach((product) => {
      initialSelections[productKey(product)] = product;
    });
    setPickerSelections(initialSelections);
    setRewardPickerOpen(true);
    setMainPickerOpen(false);
    void fetchCandidates('reward');
  };

  const addMainProduct = (product: AddOnProductRow) => {
    setMainProducts((prev) => (prev.some((item) => productKey(item) === productKey(product)) ? prev : [...prev, product]));
  };

  const addRewardProduct = (product: AddOnProductRow) => {
    const nextProduct = {
      ...product,
      addon_price: promoType === 'discount' ? (product.addon_price || product.suggested_addon_price || product.original_price) : null,
      reward_qty: Number(giftQty || '1') || 1,
    };
    setRewardProducts((prev) => (prev.some((item) => productKey(item) === productKey(product)) ? prev : [...prev, nextProduct]));
  };

  const togglePickerProduct = (product: AddOnProductRow) => {
    const key = productKey(product);
    setPickerSelections((prev) => {
      const next = { ...prev };
      if (next[key]) delete next[key];
      else next[key] = product;
      return next;
    });
  };

  const closeProductPicker = () => {
    setMainPickerOpen(false);
    setRewardPickerOpen(false);
    setPickerSelections({});
  };

  const applyProductPicker = () => {
    const selected = Object.values(pickerSelections);
    if (mainPickerOpen) {
      setMainProducts(selected);
    } else {
      setRewardProducts(selected.map((product) => ({
        ...product,
        addon_price: promoType === 'discount' ? (product.addon_price || product.suggested_addon_price || product.original_price) : null,
        reward_qty: Number(giftQty || product.reward_qty || 1) || 1,
      })));
    }
    closeProductPicker();
  };

  const buildPayload = () => ({
    draft_id: draftId,
    promotion_type: toApiPromotionType(promoType),
    campaign_name: campaignName.trim(),
    start_at: startAt,
    end_at: endAt,
    addon_purchase_limit: promoType === 'discount' ? Number(addonPurchaseLimit || '0') || null : null,
    gift_min_spend: promoType === 'gift' ? Number(giftMinSpend || '0') || null : null,
    main_products: mainProducts.map((product) => ({ listing_id: product.listing_id, variant_id: product.variant_id })),
    reward_products: rewardProducts.map((product) => ({
      listing_id: product.listing_id,
      variant_id: product.variant_id,
      addon_price: promoType === 'discount' ? product.addon_price : null,
      reward_qty: promoType === 'gift' ? Number(giftQty || product.reward_qty || 1) : product.reward_qty || 1,
    })),
  });

  const handleSaveDraft = async () => {
    if (!runId || readOnly) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/add-on/drafts`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(buildPayload()),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result?.detail || 'save failed');
      setDraftId(result.id ?? null);
      setIsBasicInfoSaved(true);
      setNotice('草稿已保存。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '草稿保存失败，请稍后重试。');
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (!runId || readOnly) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/add-on/campaigns`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(buildPayload()),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result?.detail || 'create failed');
      onBackToDiscount();
    } catch (err) {
      setError(err instanceof Error ? err.message : '加价购活动创建失败，请检查商品与规则。');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-8 py-8 custom-scrollbar">
      <div className="mx-auto max-w-[1280px] pb-20">
        
        {readOnly ? (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览该页面，但无法创建加价购活动。
          </div>
        ) : null}
        {error ? (
          <div className="mb-5 border border-red-100 bg-red-50 px-4 py-2 text-[13px] text-red-600">{error}</div>
        ) : null}
        {notice ? (
          <div className="mb-5 border border-emerald-100 bg-emerald-50 px-4 py-2 text-[13px] text-emerald-700">{notice}</div>
        ) : null}

        <div className="flex gap-4">
          {/* 左侧序号标识（保存后变打勾状态） */}
          <div className="flex w-6 shrink-0 flex-col items-center pt-6">
            {isBasicInfoSaved ? (
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-[#ee4d2d] bg-white text-[#ee4d2d]">
                <Check size={14} strokeWidth={3} />
              </div>
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#ee4d2d] text-[13px] text-white">1</div>
            )}
            <div className="my-2 w-[1px] flex-1 bg-[#e5e5e5]"></div>
          </div>

          <section className="flex-1 rounded-[3px] border border-[#e5e5e5] bg-white shadow-sm">
            {isBasicInfoSaved ? (
              // ================= 【保存后的摘要视图】 =================
              <div className="p-6">
                <div className="flex items-center justify-between border-b border-[#f0f0f0] pb-4">
                  <div className="flex items-center gap-3">
                    <h2 className="text-[16px] font-medium text-[#333]">基本信息</h2>
                    <span className="rounded-[2px] bg-[#fff1e6] px-1.5 py-0.5 text-[12px] text-[#ee4d2d]">即将开始</span>
                  </div>
                  <button 
                    onClick={() => setIsBasicInfoSaved(false)}
                    className="flex h-8 items-center gap-1.5 rounded-[3px] border border-[#d9d9d9] px-3 text-[14px] text-[#555] transition-colors hover:bg-[#f5f5f5]"
                  >
                    <Pencil size={14} />
                    编辑
                  </button>
                </div>
                <div className="mt-5 flex flex-wrap gap-y-5 text-[13px] text-[#333]">
                  <div className="w-[30%]"><span className="text-[#999]">促销类型: </span>{promoType === 'discount' ? '加价购' : '满额赠'}</div>
                  <div className="w-[30%]"><span className="text-[#999]">{promoType === 'discount' ? '加价购名称: ' : '满额赠名称: '}</span>{campaignName || '-'}</div>
                  <div className="w-[40%]"><span className="text-[#999]">活动时间: </span>{formatDateTimeText(startAt)} - {formatDateTimeText(endAt)}</div>
                  {promoType === 'discount' ? (
                    <div className="w-[100%]"><span className="text-[#999]">加价购商品限购数量: </span>{addonPurchaseLimit || '-'}</div>
                  ) : (
                    <div className="w-[100%]"><span className="text-[#999]">满额赠规则: </span>消费 RM {giftMinSpend || '0'} 可获得 {giftQty || '1'} 件赠品</div>
                  )}
                </div>
              </div>
            ) : (
              // ================= 【原来的表单视图】 =================
              <>
                <div className="border-b border-[#f0f0f0] px-8 py-5">
                  <h2 className="text-[18px] font-medium text-[#333]">基本信息</h2>
                </div>

                <div className="flex px-8 py-8">
                  <div className="flex-1 max-w-[700px]">
                    <div className="flex flex-col gap-y-8">
                      
                      {/* --- 促销类型 --- */}
                      <div className="flex items-start">
                        <div className="w-[180px] shrink-0 pt-3 pr-4 text-right text-[14px] text-[#555]">
                          促销类型
                        </div>
                        <div className="flex flex-1 gap-4">
                          <div 
                            onClick={() => !readOnly && setPromoType('discount')}
                            className={`relative flex h-[60px] w-[220px] cursor-pointer items-center rounded-[3px] border px-4 transition-colors ${
                              promoType === 'discount' ? 'border-[#ee4d2d] bg-[#fff8f6]' : 'border-[#d9d9d9] bg-white hover:border-[#ee4d2d]'
                            }`}
                          >
                            <div className="mr-3 flex h-8 w-8 items-center justify-center rounded bg-[#e8f3ff] text-[#2673dd]">
                              <ShoppingBag size={18} />
                            </div>
                            <span className={`text-[14px] ${promoType === 'discount' ? 'text-[#ee4d2d]' : 'text-[#333]'}`}>加价购</span>
                            {promoType === 'discount' && (
                              <div className="absolute right-0 top-0 h-0 w-0 border-l-[24px] border-t-[24px] border-l-transparent border-t-[#ee4d2d]">
                                <Check className="absolute -left-[14px] -top-[22px] text-white" size={12} strokeWidth={4} />
                              </div>
                            )}
                          </div>

                          <div 
                            onClick={() => !readOnly && setPromoType('gift')}
                            className={`relative flex h-[60px] w-[220px] cursor-pointer items-center rounded-[3px] border px-4 transition-colors ${
                              promoType === 'gift' ? 'border-[#ee4d2d] bg-[#fff8f6]' : 'border-[#d9d9d9] bg-white hover:border-[#ee4d2d]'
                            }`}
                          >
                            <div className="mr-3 flex h-8 w-8 items-center justify-center rounded bg-[#fff0e6] text-[#ee4d2d]">
                              <Gift size={18} />
                            </div>
                            <span className={`text-[14px] ${promoType === 'gift' ? 'text-[#ee4d2d]' : 'text-[#333]'}`}>满额赠</span>
                            {promoType === 'gift' && (
                              <div className="absolute right-0 top-0 h-0 w-0 border-l-[24px] border-t-[24px] border-l-transparent border-t-[#ee4d2d]">
                                <Check className="absolute -left-[14px] -top-[22px] text-white" size={12} strokeWidth={4} />
                              </div>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* --- 名称输入框 --- */}
                      <div className="flex items-start">
                        <div className="w-[180px] shrink-0 pt-2 pr-4 text-right text-[14px] text-[#555]">
                          {promoType === 'discount' ? '加价购名称' : '满额赠名称'}
                        </div>
                        <div className="flex-1 max-w-[456px]">
                          <input
                            type="text"
                            disabled={readOnly}
                            value={campaignName}
                            onChange={(event) => setCampaignName(event.target.value.slice(0, 25))}
                            placeholder="请输入"
                            className="h-10 w-full rounded-[3px] border border-[#ee4d2d] px-3 text-[14px] text-[#333] outline-none transition-colors focus:border-[#ee4d2d] focus:shadow-[0_0_0_2px_rgba(238,77,45,0.1)]"
                          />
                          <div className="mt-1 text-[12px] text-[#ee4d2d]">最多 25 个字符</div>
                          <div className="mt-0.5 text-[12px] text-[#999]">
                            {promoType === 'discount' ? '加价购名称仅供卖家参考，买家不可见。' : '满额赠名称仅供卖家参考，买家不可见。'}
                          </div>
                        </div>
                      </div>

                      {/* --- 活动时间 --- */}
                      <div className="flex items-start">
                        <div className="w-[180px] shrink-0 pt-2 pr-4 text-right text-[14px] text-[#555]">
                          活动时间
                        </div>
                        <div className="flex-1 max-w-[456px]">
                          <div className="flex items-center gap-3">
                            <DateTimePicker
                              value={startAt}
                              onChange={setStartAt}
                              inputWidthClassName="w-[180px]"
                              popupPlacement="bottom"
                            />
                            <span className="text-[#999]">—</span>
                            <DateTimePicker
                              value={endAt}
                              onChange={setEndAt}
                              inputWidthClassName="w-[180px]"
                              popupPlacement="bottom"
                            />
                          </div>
                          <div className="mt-1.5 text-[12px] text-[#999] leading-[18px]">
                            结束时间必须晚于开始时间至少 1 小时。<br/>
                            活动保存成功后，活动时间只能缩短。
                          </div>
                        </div>
                      </div>

                      {/* --- 规则设置区 --- */}
                      {promoType === 'discount' ? (
                        <div className="flex items-start">
                          <div className="w-[180px] shrink-0 pt-2 pr-4 text-right text-[14px] text-[#555]">
                            加价购商品限购数量
                          </div>
                          <div className="flex-1 max-w-[456px]">
                            <input
                              type="text"
                              disabled={readOnly}
                              value={addonPurchaseLimit}
                              onChange={(event) => setAddonPurchaseLimit(event.target.value.replace(/[^0-9]/g, '').slice(0, 2))}
                              placeholder="请输入小于 100 的数量"
                              className="h-10 w-full rounded-[3px] border border-[#d9d9d9] px-3 text-[14px] text-[#333] outline-none transition-colors hover:border-[#b4b4b4] focus:border-[#ee4d2d]"
                            />
                            <div className="mt-1.5 text-[12px] text-[#999] leading-[18px]">
                              买家在每个加价购活动中可购买的加价购商品最大数量。
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start">
                          <div className="w-[180px] shrink-0 pt-2 pr-4 text-right text-[14px] text-[#555]">
                            满额赠规则
                          </div>
                          <div className="flex-1 max-w-[456px]">
                            <div className="flex items-center gap-3 text-[14px] text-[#555]">
                              <span>消费</span>
                              <div className="flex h-10 w-[120px] items-center rounded-[3px] border border-[#d9d9d9] bg-white px-3 focus-within:border-[#ee4d2d] focus-within:shadow-[0_0_0_2px_rgba(238,77,45,0.1)]">
                                <span className="text-[#999] mr-2">RM</span>
                                <input
                                  type="text"
                                  disabled={readOnly}
                                  value={giftMinSpend}
                                  onChange={(event) => setGiftMinSpend(event.target.value.replace(/[^0-9.]/g, ''))}
                                  className="w-full outline-none text-[#333] bg-transparent"
                                />
                              </div>
                              <span>可获得</span>
                              <div className="flex h-10 flex-1 items-center rounded-[3px] border border-[#d9d9d9] bg-white px-3 focus-within:border-[#ee4d2d] focus-within:shadow-[0_0_0_2px_rgba(238,77,45,0.1)]">
                                <input
                                  type="text"
                                  disabled={readOnly}
                                  value={giftQty}
                                  onChange={(event) => setGiftQty(event.target.value.replace(/[^0-9]/g, '').slice(0, 2))}
                                  placeholder="数量小于 50"
                                  className="w-full outline-none text-[#333] bg-transparent placeholder:text-[#bfbfbf]"
                                />
                              </div>
                              <span>件赠品</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* --- 保存按钮 --- */}
                      <div className="flex items-start mt-2">
                        <div className="w-[180px] shrink-0 pr-4"></div>
                        <div className="flex-1 max-w-[456px]">
                          <button
                            disabled={readOnly || saving}
                            onClick={handleSaveDraft}
                            className="h-10 w-[80px] rounded-[3px] bg-[#ee4d2d] text-[14px] font-medium text-white transition-colors hover:bg-[#d73f22] disabled:opacity-50"
                          >
                            {saving ? '保存中' : '保存'}
                          </button>
                        </div>
                      </div>

                    </div>
                  </div>

                  {/* --- 手机预览区 --- */}
                  <div 
                    className="w-[280px] flex-shrink-0" 
                    style={{ 
                      marginTop: '-120px',
                      marginLeft: '100px' 
                    }} 
                  >
                    <div className="relative mx-auto h-[560px] w-[280px]">
                      
                      <div 
                        className="absolute z-30"
                        style={{
                          top: '38px',     
                          left: '18px',    
                          right: '18px',
                          bottom: '42px',
                          borderRadius: '22px', 
                        }}
                      >               
                        <img 
                          src="https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/src/assets/preview/base_info_th.svg" 
                          alt="ui-overlay"
                          className="absolute bottom-25 left-0 w-full"
                          style={{ height: 'auto' }}
                        />
                      </div>

                      <img 
                        src="https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/mmf_portal_seller_root_dir/static/modules/bundle-deal-v2/image/phone_bg.076ca95.png" 
                        className="absolute inset-0 z-20 h-full w-full object-contain pointer-events-none"
                        alt="phone frame"
                      />
                    </div>
                    <div className="-mt-28 text-center text-[12px] text-[#999] leading-relaxed px-2 relative z-20">
                      {promoType === 'discount' 
                        ? '买家将在主商品详情页和购物车中看到加价购商品' 
                        : '购买任何商品达到最低消费即可获得赠品'}
                    </div>
                  </div>

                </div>
              </>
            )}
          </section>
        </div>

        <div className="flex gap-4 mt-4">
          <div className="flex w-6 shrink-0 flex-col items-center pt-4">
            {isBasicInfoSaved ? (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#ee4d2d] text-[13px] text-white">2</div>
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-[#d9d9d9] bg-white text-[13px] text-[#999]">2</div>
            )}
            <div className="my-2 w-[1px] flex-1 bg-[#e5e5e5]"></div>
          </div>
          <section className={`flex-1 rounded-[3px] border border-[#e5e5e5] bg-white px-8 py-5 shadow-sm ${isBasicInfoSaved ? '' : 'opacity-60 pointer-events-none'}`}>
            <div>
              <h2 className={`text-[18px] font-medium ${isBasicInfoSaved ? 'text-[#333]' : 'text-[#999]'}`}>主商品</h2>
              <div className="mt-1 text-[14px] text-[#999]">买家在同一个加价购活动中最多可购买 100 件主商品。</div>
            </div>
            
            {/* 只有在第一步保存后，才显示添加按钮 */}
            {isBasicInfoSaved && (
              <div className="mt-5">
                <button 
                  type="button" 
                  disabled={readOnly || loadingProducts} 
                  onClick={handleOpenMainPicker} 
                  className="flex h-9 items-center justify-center gap-1.5 rounded-[3px] border border-[#ee4d2d] px-4 text-[14px] text-[#ee4d2d] transition-colors hover:bg-[#fff8f6] disabled:opacity-50"
                >
                  <Plus size={16} />
                  添加主商品
                </button>
              </div>
            )}
            {mainProducts.length ? (
              <div className="mt-5 rounded-[3px] border border-[#e5e5e5]">
                {/* --- 修改点 1：表头调整为 4 列比例 [5fr_2fr_1.5fr_1fr] --- */}
                <div className="grid grid-cols-[5fr_2fr_1.5fr_1fr] bg-[#fafafa] px-4 py-3 text-[13px] text-[#999]">
                  <div>商品</div>
                  <div>当前价格</div>
                  <div>库存</div>
                  <div className="text-right">操作</div>
                </div>
                
                {/* --- 修改点 2：列表内容对应调整为 4 列比例，并删掉发货天数数据 --- */}
                <div className="divide-y divide-[#f5f5f5]">
                  {mainProducts.map((product) => (
                    <div key={productKey(product)} className="grid grid-cols-[5fr_2fr_1.5fr_1fr] items-center px-4 py-4 text-[13px] text-[#333]">
                      
                      {/* 商品列 (自带 min-w-0 防止长文本撑破布局) */}
                      <div className="flex min-w-0 items-center gap-3 pr-4">
                        <div 
                          className="h-12 w-12 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5] bg-cover bg-center" 
                          style={product.image_url ? { backgroundImage: `url(${product.image_url})` } : undefined} 
                        />
                        <div className="min-w-0">
                          <div className="truncate text-[14px] leading-tight text-[#333]">{product.product_name}</div>
                          {product.variant_name && <div className="mt-1.5 truncate text-[12px] text-[#999]">{product.variant_name}</div>}
                        </div>
                      </div>
                      
                      {/* 价格列 */}
                      <div>RM {product.original_price.toFixed(2)}</div>
                      
                      {/* 库存列 */}
                      <div>{product.stock_available}</div>
                      
                      {/* 操作列 */}
                      <div className="text-right">
                        <button 
                          type="button" 
                          onClick={() => setMainProducts((prev) => prev.filter((item) => productKey(item) !== productKey(product)))} 
                          className="text-[#ee4d2d] transition-colors hover:text-[#d73f22]"
                        >
                          移除
                        </button>
                      </div>

                    </div>
                  ))}
                </div>
                
                {/* 底部分页组件 (保持不变) */}
                <div className="flex items-center justify-end gap-4 border-t border-[#e5e5e5] bg-[#fafafa] px-4 py-3 text-[13px] text-[#555]">
                  <div className="flex items-center gap-1">
                    <button className="flex h-7 w-7 cursor-not-allowed items-center justify-center text-[#ccc]">{'<'}</button>
                    <button className="flex h-7 w-7 items-center justify-center text-[#ee4d2d]">1</button>
                    <button className="flex h-7 w-7 cursor-not-allowed items-center justify-center text-[#ccc]">{'>'}</button>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>前往</span>
                    <input type="text" defaultValue="1" className="h-7 w-10 rounded-[2px] border border-[#d9d9d9] text-center outline-none focus:border-[#ee4d2d]" />
                    <span>页</span>
                    <button className="ml-2 h-7 rounded-[2px] border border-[#d9d9d9] bg-white px-3 hover:bg-[#f5f5f5]">
                      确认
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </section>
        </div>

        <div className="flex gap-4 mt-4">
          <div className="flex w-6 shrink-0 flex-col items-center pt-4">
            {mainProducts.length > 0 ? (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#ee4d2d] text-[13px] text-white">3</div>
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-[#d9d9d9] bg-white text-[13px] text-[#999]">3</div>
            )}
          </div>
          <section className={`flex-1 rounded-[3px] border border-[#e5e5e5] bg-white px-8 py-5 shadow-sm ${mainProducts.length > 0 ? '' : 'opacity-60 pointer-events-none'}`}>
            <div>
              <h2 className={`text-[18px] font-medium ${mainProducts.length > 0 ? 'text-[#333]' : 'text-[#999]'}`}>{promoType === 'discount' ? '加价购商品' : '赠品商品'}</h2>
              <div className="mt-1 text-[14px] text-[#999]">{promoType === 'discount' ? '买家购买任何主商品时，均可享受加价购商品的折扣价。' : '买家满足满额赠规则后，可获得赠品。'}</div>
            </div>

            {/* 只有在选了主商品之后，才显示这个按钮 */}
            {mainProducts.length > 0 && (
              <div className="mt-5">
                <button 
                  type="button" 
                  disabled={readOnly || loadingProducts} 
                  onClick={handleOpenRewardPicker} 
                  className="flex h-9 items-center justify-center gap-1.5 rounded-[3px] border border-[#ee4d2d] px-4 text-[14px] text-[#ee4d2d] transition-colors hover:bg-[#fff8f6] disabled:opacity-50"
                >
                  <Plus size={16} />
                  {promoType === 'discount' ? '添加加价购商品' : '添加赠品商品'}
                </button>
              </div>
            )}
            {rewardProducts.length ? (
              <div className="mt-5">
                {/* 整体表格表头 (7列布局) */}
                <div className="grid grid-cols-[2.5fr_1.5fr_2fr_1.5fr_1fr_1fr_1fr] rounded-t-[3px] border border-[#e5e5e5] border-b-0 bg-[#fafafa] px-4 py-3 text-[13px] text-[#999]">
                  <div>规格</div>
                  <div>当前价格</div>
                  <div>{promoType === 'discount' ? '加价购价格' : '赠品价格'}</div>
                  <div>折扣</div>
                  <div>库存</div>
                  <div>购买限制</div>
                  <div className="text-right">操作</div>
                </div>

                {/* 按主商品分组渲染 */}
                <div className="flex flex-col gap-4">
                  {Object.values(
                    rewardProducts.reduce((acc, curr) => {
                      if (!acc[curr.listing_id]) acc[curr.listing_id] = [];
                      acc[curr.listing_id].push(curr);
                      return acc;
                    }, {} as Record<number, typeof rewardProducts>)
                  ).map((group) => {
                    const mainProduct = group[0];
                    return (
                      <div key={mainProduct.listing_id} className="rounded-[3px] border border-[#e5e5e5]">
                        {/* 组头：商品图片和名称 */}
                        <div className="flex items-center gap-3 border-b border-[#e5e5e5] bg-[#fafafa] px-4 py-3">
                          <div 
                            className="h-8 w-8 flex-shrink-0 border border-[#ececec] bg-white bg-cover bg-center" 
                            style={mainProduct.image_url ? { backgroundImage: `url(${mainProduct.image_url})` } : undefined} 
                          />
                          <div className="truncate text-[13px] font-medium text-[#333]">{mainProduct.product_name}</div>
                        </div>
                        
                        {/* 组内 SKU 列表 */}
                        <div className="divide-y divide-[#f5f5f5]">
                          {group.map((product) => {
                            // 动态计算折扣百分比
                            let discountPercent = 0;
                            if (promoType === 'gift') {
                              discountPercent = 100; // 赠品相当于 100% OFF
                            } else if (product.addon_price != null && product.original_price > 0) {
                              discountPercent = Math.max(0, Math.round((1 - product.addon_price / product.original_price) * 100));
                            }

                            return (
                              <div key={productKey(product)} className="grid grid-cols-[2.5fr_1.5fr_2fr_1.5fr_1fr_1fr_1fr] items-center px-4 py-4 text-[13px] text-[#333]">
                                <div className="truncate pr-4 text-[#666]">{product.variant_name || '单规格'}</div>
                                <div>RM {product.original_price.toFixed(2)}</div>
                                
                                {/* 价格列 */}
                                <div className="pr-4">
                                  {promoType === 'discount' ? (
                                    <div className="flex h-8 w-full max-w-[120px] items-center rounded-[2px] border border-[#d9d9d9] bg-white px-2 focus-within:border-[#ee4d2d]">
                                      <span className="text-[#999] mr-1 text-[12px]">RM</span>
                                      <input 
                                        type="number"
                                        value={product.addon_price ?? ''}
                                        onChange={(e) => {
                                          const val = e.target.value ? Number(e.target.value) : null;
                                          setRewardProducts(prev => prev.map(p => productKey(p) === productKey(product) ? { ...p, addon_price: val } : p));
                                        }}
                                        className="w-full bg-transparent text-[13px] outline-none"
                                      />
                                    </div>
                                  ) : (
                                    <span className="text-[#666]">RM 0.00</span>
                                  )}
                                </div>

                                {/* 折扣百分比 (红框) */}
                                <div>
                                  {discountPercent > 0 ? (
                                    <span className="inline-block rounded-[2px] border border-[#ee4d2d] px-1.5 py-0.5 text-[11px] font-medium leading-none text-[#ee4d2d]">
                                      {discountPercent}%OFF
                                    </span>
                                  ) : (
                                    <span className="text-[#999]">-</span>
                                  )}
                                </div>

                                <div>{product.stock_available}</div>
                                
                                <div className="text-[#999]">无限制</div>
                                
                                <div className="text-right">
                                  <button 
                                    type="button" 
                                    onClick={() => setRewardProducts((prev) => prev.filter((item) => productKey(item) !== productKey(product)))} 
                                    className="text-[#ee4d2d] transition-colors hover:text-[#d73f22]"
                                  >
                                    移除
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </section>
        </div>

        <div className="mt-8 flex justify-end gap-3 px-10">
          <button
            type="button"
            onClick={onBackToDiscount}
            className="flex h-[36px] min-w-[80px] items-center justify-center rounded-[3px] border border-[#d9d9d9] bg-white px-4 text-[14px] text-[#555] transition-colors hover:bg-[#f5f5f5]"
          >
            取消
          </button>
          <button
            type="button"
            disabled={readOnly || saving}
            onClick={handleConfirm}
            className="flex h-[36px] min-w-[80px] items-center justify-center rounded-[3px] bg-[#ee4d2d] px-6 text-[14px] text-white transition-colors hover:bg-[#d73f22] disabled:opacity-50"
          >
            {saving ? '提交中' : '确认'}
          </button>
        </div>

      </div>

      {(mainPickerOpen || rewardPickerOpen) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(15,23,42,0.32)]">
          <div className="flex h-[676px] w-[950px] flex-col border border-[#ececec] bg-white shadow-[0_18px_60px_rgba(15,23,42,0.22)]">
            <div className="flex items-center justify-between px-6 pb-2 pt-6">
              <div className="text-[18px] font-semibold text-[#2f2f2f]">选择商品</div>
              <button type="button" onClick={closeProductPicker} className="text-[#888] hover:text-[#333]">
                <X size={18} />
              </button>
            </div>
            <div className="border-b border-[#efefef] px-6">
              <div className="flex items-end gap-7 text-[14px]">
                <button type="button" className="border-b-2 border-[#ee4d2d] px-4 py-3 font-medium text-[#ee4d2d]">
                  选择商品
                </button>
                <button type="button" className="border-b-2 border-transparent px-1 py-3 font-medium text-[#666]">
                  上传商品列表
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden px-6 py-4">
              <div className="grid grid-cols-[72px_210px_64px_160px_1fr] items-center gap-3 text-[14px] text-[#555]">
                <div>分类</div>
                <button type="button" className="flex h-10 w-full items-center justify-between border border-[#d9d9d9] bg-white px-4 text-left text-[14px] text-[#555]">
                  <span>全部</span>
                </button>
                <div>搜索</div>
                <button type="button" className="flex h-10 w-full items-center justify-between border border-[#d9d9d9] bg-white px-4 text-left text-[14px] text-[#555]">
                  <span>商品名称</span>
                </button>
                <div className="flex h-10 items-center border border-[#d9d9d9] bg-white px-3">
                  <input disabled placeholder="请输入" className="w-full bg-transparent text-[14px] outline-none placeholder:text-[#b7b7b7]" />
                </div>
              </div>
              <div className="mt-4 flex h-[470px] flex-col border border-[#efefef]">
                <div className="grid grid-cols-[50px_1.9fr_0.7fr_0.8fr_0.8fr] bg-[#fafafa] px-4 py-3 text-[13px] font-medium text-[#666]">
                  <div />
                  <div>商品</div>
                  <div>状态</div>
                  <div>价格</div>
                  <div>库存</div>
                </div>
                {loadingProducts ? (
                  <div className="space-y-3 p-4">
                    {Array.from({ length: 5 }).map((_, index) => (
                      <div key={index} className="h-12 animate-pulse bg-[#f3f3f3]" />
                    ))}
                  </div>
                ) : (mainPickerOpen ? mainCandidates : rewardCandidates).length ? (
                  <div className="flex-1 overflow-y-auto custom-scrollbar">
                    {(mainPickerOpen ? mainCandidates : rewardCandidates).map((product) => {
                      const key = productKey(product);
                      const checked = Boolean(pickerSelections[key]);
                      const disabledRow = product.stock_available <= 0;
                      return (
                        <div key={key} className="grid grid-cols-[50px_1.9fr_0.7fr_0.8fr_0.8fr] items-center border-t border-[#f1f1f1] px-4 py-3 text-[14px] text-[#444]">
                          <div>
                            <button
                              type="button"
                              onClick={() => {
                                if (!disabledRow) togglePickerProduct(product);
                              }}
                              className={`flex h-[18px] w-[18px] items-center justify-center border ${
                                checked ? 'border-[#ee4d2d] bg-[#ee4d2d]' : 'border-[#d9d9d9] bg-white'
                              } ${disabledRow ? 'cursor-not-allowed opacity-40' : ''}`}
                              aria-pressed={checked}
                              disabled={disabledRow}
                            >
                              {checked ? <Check size={12} className="text-white" /> : null}
                            </button>
                          </div>
                          <div className="flex min-w-0 items-center gap-3 pr-4">
                            <div className="h-10 w-10 flex-shrink-0 border border-[#ececec] bg-[#f5f5f5]" style={product.image_url ? { backgroundImage: `url(${product.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined} />
                            <div className="min-w-0">
                              <div className="truncate font-medium text-[#333]">{product.product_name}</div>
                              <div className="mt-1 truncate text-[12px] text-[#8a8a8a]">
                                {product.variant_name ? `规格：${product.variant_name}` : '单规格商品'}
                                {product.sku ? ` · SKU：${product.sku}` : ''}
                              </div>
                            </div>
                          </div>
                          <div className="text-[#666]">-</div>
                          <div className="text-[#555]">RM {product.original_price.toFixed(2)}</div>
                          <div className={disabledRow ? 'text-[#d14343]' : 'text-[#555]'}>{product.stock_available}</div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center text-[#9a9a9a]">
                    <div className="flex h-16 w-16 items-center justify-center border border-[#ededed] bg-[#fafafa] text-[#d6d6d6]">
                      <PackageOpen size={28} />
                    </div>
                    <div className="text-[14px]">未找到符合条件的商品</div>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-[#efefef] px-6 py-4">
              <button type="button" onClick={closeProductPicker} className="h-9 border border-[#d9d9d9] bg-white px-5 text-[14px] text-[#555] hover:bg-[#fafafa]">
                取消
              </button>
              <button type="button" onClick={applyProductPicker} className="h-9 bg-[#ee4d2d] px-5 text-[14px] font-medium text-white hover:bg-[#d83f21]">
                确认
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
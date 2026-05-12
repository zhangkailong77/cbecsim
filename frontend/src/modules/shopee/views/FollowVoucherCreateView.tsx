import { useState, useEffect } from 'react';
import DateTimePicker from '../components/DateTimePicker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type DiscountType = 'fixed_amount' | 'percent';
type MaxDiscountType = 'set_amount' | 'no_limit';

interface FollowVoucherCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  detailCampaignId?: number | null;
  onBackToVouchers: () => void;
}

interface FollowVoucherCreateBootstrapResponse {
  meta: {
    read_only: boolean;
    currency: string;
  };
  form: {
    voucher_name: string;
    claim_start_at: string;
    claim_end_at: string;
    discount_type: DiscountType;
    discount_amount: number | null;
    discount_percent: number | null;
    max_discount_type: MaxDiscountType;
    max_discount_amount: number | null;
    min_spend_amount: number | null;
    usage_limit: number | null;
    per_buyer_limit: number;
  };
}

// 关注礼预览轮播图素材
const basePreviewImages =[
  'https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/mmf_portal_seller_root_dir/static/modules/follow-prize/image/1.b5b2ffd.png',
  'https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/mmf_portal_seller_root_dir/static/modules/follow-prize/image/2.dbb36c2.png'
];
// 在末尾克隆第一张图，用于实现无缝循环向左滑
const previewImages = [...basePreviewImages, basePreviewImages[0]];

export default function FollowVoucherCreateView({ runId, readOnly = false, detailCampaignId = null, onBackToVouchers }: FollowVoucherCreateViewProps) {
  // 基础信息状态
  const[voucherName, setVoucherName] = useState('');
  const [claimStartAt, setClaimStartAt] = useState('');
  const [claimEndAt, setClaimEndAt] = useState('');

  // 奖励设置状态
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const[discountType, setDiscountType] = useState<DiscountType>('fixed_amount');
  const[maxDiscountType, setMaxDiscountType] = useState<MaxDiscountType>('set_amount');
  const [discountAmount, setDiscountAmount] = useState('');
  const[discountPercent, setDiscountPercent] = useState('');
  const [maxDiscountAmount, setMaxDiscountAmount] = useState('');
  const [minSpendAmount, setMinSpendAmount] = useState('');
  const [usageLimit, setUsageLimit] = useState('');
  const [perBuyerLimit, setPerBuyerLimit] = useState('1');

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [currency, setCurrency] = useState('RM');

  // 轮播图状态
  const [currentPreviewIndex, setCurrentPreviewIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(true);

  const effectiveReadOnly = readOnly || serverReadOnly;

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setError('');
    const endpoint = detailCampaignId
      ? `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/detail/follow_voucher/${detailCampaignId}`
      : `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/follow-create/bootstrap`;
    fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        if (!response.ok) {
          const result = await response.json().catch(() => null);
          throw new Error(result?.detail || (detailCampaignId ? '详情页加载失败，请稍后重试。' : '创建页初始化失败，请稍后重试。'));
        }
        return response.json() as Promise<FollowVoucherCreateBootstrapResponse>;
      })
      .then((result) => {
        if (cancelled) return;
        setServerReadOnly(Boolean(result.meta.read_only || detailCampaignId));
        setCurrency(result.meta.currency || 'RM');
        setVoucherName(result.form.voucher_name || '');
        setClaimStartAt(result.form.claim_start_at || '');
        setClaimEndAt(result.form.claim_end_at || '');
        setDiscountType(result.form.discount_type || 'fixed_amount');
        setDiscountAmount(result.form.discount_amount == null ? '' : String(result.form.discount_amount));
        setDiscountPercent(result.form.discount_percent == null ? '' : String(result.form.discount_percent));
        setMaxDiscountType(result.form.max_discount_type || 'set_amount');
        setMaxDiscountAmount(result.form.max_discount_amount == null ? '' : String(result.form.max_discount_amount));
        setMinSpendAmount(result.form.min_spend_amount == null ? '' : String(result.form.min_spend_amount));
        setUsageLimit(result.form.usage_limit == null ? '' : String(result.form.usage_limit));
        setPerBuyerLimit(String(result.form.per_buyer_limit || 1));
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

  const validateForm = () => {
    if (!voucherName.trim()) return '请输入代金券名称。';
    if (!claimStartAt || !claimEndAt) return '请选择领取期限。';
    if (claimStartAt >= claimEndAt) return '领取结束时间必须晚于开始时间。';
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
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/follow-campaigns`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voucher_type: 'follow_voucher',
          voucher_name: voucherName.trim(),
          claim_start_at: claimStartAt,
          claim_end_at: claimEndAt,
          reward_type: 'discount',
          discount_type: discountType,
          discount_amount: discountType === 'fixed_amount' ? Number(discountAmount) : null,
          discount_percent: discountType === 'percent' ? Number(discountPercent) : null,
          max_discount_type: discountType === 'percent' ? maxDiscountType : 'set_amount',
          max_discount_amount: discountType === 'percent' && maxDiscountType === 'set_amount' ? Number(maxDiscountAmount) : null,
          min_spend_amount: Number(minSpendAmount),
          usage_limit: Number(usageLimit),
          per_buyer_limit: Number(perBuyerLimit),
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

  // 自动滑动定时器（每3秒执行一次）
  useEffect(() => {
    const timer = setInterval(() => {
      setIsTransitioning(true); // 开启过渡动画
      setCurrentPreviewIndex((prev) => prev + 1); // 始终加1，一直向左滑
    }, 3000);
    return () => clearInterval(timer);
  },[]);

  // 监听轮播到达克隆的第一张图时，瞬间无缝切回真正的第一张图
  useEffect(() => {
    if (currentPreviewIndex === basePreviewImages.length) {
      const timeout = setTimeout(() => {
        setIsTransitioning(false); // 关闭过渡动画
        setCurrentPreviewIndex(0); // 瞬间跳回真实的第 1 张图
      }, 500); // 500ms 必须与下方 css 的 duration-500 动画时长保持一致
      return () => clearTimeout(timeout);
    }
  }, [currentPreviewIndex]);

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
              
              {/* ================= 基础信息 (Basic Information) ================= */}
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">基础信息</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  
                  <div className="pt-2 text-right pr-6">代金券类型</div>
                  <div>
                    <div className="relative flex h-[40px] w-[180px] items-center justify-center rounded-sm border border-[#ee4d2d] bg-white text-[#ee4d2d] cursor-pointer">
                      <svg viewBox="0 0 24 24" className="mr-2 h-[18px] w-[18px]" fill="currentColor">
                        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                      </svg>
                      关注礼代金券
                      <div className="absolute right-0 top-0 h-0 w-0 border-l-[16px] border-t-[16px] border-l-transparent border-t-[#ee4d2d]"></div>
                      <svg className="absolute right-[1px] top-[1px] h-[10px] w-[10px] text-white" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M13.485 1.431a1.473 1.473 0 0 1 2.104 2.062l-7.84 9.802a1.473 1.473 0 0 1-2.12.04L.431 8.138a1.473 1.473 0 0 1 2.084-2.083l4.111 4.112 6.82-8.65a.486.486 0 0 1 .04-.086z" />
                      </svg>
                    </div>
                  </div>

                  <div className="pt-2 text-right pr-6">代金券名称</div>
                  <div className="max-w-[700px]">
                    <div className="flex h-9 w-full items-center rounded-sm border border-[#e5e5e5] px-3 focus-within:border-[#ee4d2d]">
                      <input type="text" value={voucherName} onChange={(e) => setVoucherName(e.target.value.slice(0, 20))} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] disabled:bg-white" placeholder="请输入" />
                      <span className="text-[12px] text-[#999]">{voucherName.length}/20</span>
                    </div>
                    <div className="mt-2 text-[12px] text-[#999]">代金券名称仅卖家可见，不向买家展示。</div>
                  </div>

                  <div className="pt-1 text-right pr-6">代金券代码</div>
                  <div className="pt-1 text-[14px] text-[#333]">
                    代金券代码将自动生成
                  </div>

                  <div className="pt-2 text-right pr-6">领取期限</div>
                  <div className="max-w-[700px]">
                    <div className="flex items-center gap-3">
                      <DateTimePicker value={claimStartAt} onChange={effectiveReadOnly ? () => undefined : setClaimStartAt} inputWidthClassName="w-[180px]" popupPlacement="bottom" maxValue={claimEndAt || undefined} />
                      <span className="w-[18px] text-center text-[14px] text-[#999]">至</span>
                      <DateTimePicker value={claimEndAt} onChange={effectiveReadOnly ? () => undefined : setClaimEndAt} inputWidthClassName="w-[180px]" popupPlacement="bottom" minValue={claimStartAt || undefined} />
                    </div>
                  </div>

                  <div className="pt-1 text-right pr-6">有效期限</div>
                  <div className="pt-1 text-[14px] text-[#333]">
                    领取代金券后 7 天内有效
                  </div>

                </div>
              </section>

              {/* ================= 奖励设置 (Reward Settings) ================= */}
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">奖励设置</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  
                  <div className="pt-1 text-right pr-6">奖励类型</div>
                  <div className="flex items-center gap-6">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="followRewardType" checked readOnly className="h-4 w-4 accent-[#ee4d2d]" />
                      <span>折扣</span>
                    </label>
                  </div>

                  <div className="pt-2 text-right pr-6">折扣类型 | 金额</div>
                  <div className="max-w-[700px]">
                    <div className="flex items-center gap-3">
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
                        <input type="number" value={discountType === 'fixed_amount' ? discountAmount : discountPercent} onChange={(e) => discountType === 'fixed_amount' ? setDiscountAmount(e.target.value) : setDiscountPercent(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" placeholder="输入" />
                        {discountType === 'percent' && <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-l border-[#e5e5e5] text-[#999] text-[12px]">%OFF</div>}
                      </div>
                    </div>
                    <div className="mt-2 text-[12px] text-[#999]">通过提供有吸引力的折扣代金券，吸引用户关注您的店铺。</div>
                  </div>

                  {/* 百分比的最大折扣金额联动 */}
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
                            <input type="number" value={maxDiscountAmount} onChange={(e) => setMaxDiscountAmount(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" placeholder="输入" />
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  <div className="pt-2 text-right pr-6">最低消费金额</div>
                  <div className="max-w-[700px]">
                    <div className="flex h-9 w-[452px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                      <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>
                      <input type="number" value={minSpendAmount} onChange={(e) => setMinSpendAmount(e.target.value)} disabled={effectiveReadOnly} className="flex-1 outline-none text-[14px] px-3 disabled:bg-white" placeholder="输入" />
                    </div>
                  </div>

                  <div className="pt-2 text-right pr-6">使用数量</div>
                  <div className="max-w-[700px]">
                    <input type="number" value={usageLimit} onChange={(e) => setUsageLimit(e.target.value)} disabled={effectiveReadOnly} className="h-9 w-[452px] rounded-sm border border-[#e5e5e5] px-3 text-[14px] outline-none focus:border-[#ee4d2d] disabled:bg-white" placeholder="输入" />
                    <div className="mt-2 text-[12px] text-[#999]">最大可领取并使用代金券数量</div>
                  </div>

                </div>
              </section>

              {/* ================= 代金券展示与适用商品 ================= */}
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">代金券展示与适用商品</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  
                  <div className="pt-1 text-right pr-6">适用商品</div>
                  <div className="flex items-center gap-2 pt-1">
                    <span>全部商品</span>
                    <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px] cursor-pointer">?</span>
                  </div>

                </div>
              </section>
            </div>

            {/* 吸底操作栏 */}
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

          {/* ================= 右侧手机预览图 (带无缝单向滑动轮播) ================= */}
          <div className="w-[320px] shrink-0 sticky top-0">
            <div className="border border-[#ececec] bg-white p-5 shadow-sm rounded-[2px]">
              <div className="text-[16px] font-medium text-[#333] mb-4">预览</div>
              
              {/* 隐藏超出的部分 */}
              <div className="relative mx-auto h-[310px] w-full overflow-hidden">
                {/* 轮播容器：根据 isTransitioning 状态决定是否开启平滑过渡 */}
                <div 
                  className={`flex h-full w-full ${isTransitioning ? 'transition-transform duration-500 ease-in-out' : ''}`}
                  style={{ transform: `translateX(-${currentPreviewIndex * 100}%)` }}
                >
                  {previewImages.map((src, index) => (
                    <div
                      key={index}
                      className="h-full w-full flex-shrink-0 bg-top bg-no-repeat bg-contain"
                      style={{ backgroundImage: `url("${src}")` }}
                    />
                  ))}
                </div>
              </div>
              
              {/* 轮播指示点 (只根据真实的图片数量进行循环取余渲染) */}
              <div className="mt-3 flex justify-center gap-2">
                {basePreviewImages.map((_, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      setIsTransitioning(true);
                      setCurrentPreviewIndex(index);
                    }}
                    className={`h-[6px] w-[6px] rounded-full transition-colors ${
                      (currentPreviewIndex % basePreviewImages.length) === index ? 'bg-[#b4b4b4]' : 'bg-[#e6e6e6]'
                    }`}
                  />
                ))}
              </div>

              <div className="mt-4 text-[11px] text-[#999] text-center px-4">
                买家可以在店铺内的所有商品上使用此代金券。
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
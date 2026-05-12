import { useEffect, useState } from 'react';
import DateTimePicker from '../components/DateTimePicker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type DiscountType = 'fixed_amount' | 'percent';
type MaxDiscountType = 'set_amount' | 'no_limit';
type DisplayType = 'all_pages' | 'specific_channels' | 'code_only';

interface ShopVoucherCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  detailCampaignId?: number | null;
  onBackToVouchers: () => void;
}

interface VoucherCreateBootstrapResponse {
  meta: {
    read_only: boolean;
    currency: string;
  };
  form: {
    voucher_name: string;
    code_prefix: string;
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
  voucher_code: string;
  available: boolean;
  message: string;
}

interface VoucherDetailResponse extends VoucherCreateBootstrapResponse {
  voucher_code: string;
}

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

export default function ShopVoucherCreateView({ runId, readOnly = false, detailCampaignId = null, onBackToVouchers }: ShopVoucherCreateViewProps) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [codeCheck, setCodeCheck] = useState<VoucherCodeCheckResponse | null>(null);
  const [codeChecking, setCodeChecking] = useState(false);
  const [currency, setCurrency] = useState('RM');
  const [serverReadOnly, setServerReadOnly] = useState(false);
  const [voucherName, setVoucherName] = useState('');
  const [codePrefix, setCodePrefix] = useState('HOME');
  const [codeSuffix, setCodeSuffix] = useState('');
  const [discountType, setDiscountType] = useState<DiscountType>('fixed_amount');
  const [maxDiscountType, setMaxDiscountType] = useState<MaxDiscountType>('set_amount');
  const [voucherStartAt, setVoucherStartAt] = useState('');
  const [voucherEndAt, setVoucherEndAt] = useState('');
  const [displayBeforeStart, setDisplayBeforeStart] = useState(false);
  const [displayStartAt, setDisplayStartAt] = useState(''); // 新增：提前展示的时间状态
  const [discountAmount, setDiscountAmount] = useState('');
  const [discountPercent, setDiscountPercent] = useState('');
  const [maxDiscountAmount, setMaxDiscountAmount] = useState('');
  const [minSpendAmount, setMinSpendAmount] = useState('');
  const [usageLimit, setUsageLimit] = useState('');
  const [perBuyerLimit, setPerBuyerLimit] = useState('1');
  const [displayType, setDisplayType] = useState<DisplayType>('all_pages');
  const [displayChannels, setDisplayChannels] = useState<string[]>([]);

  const effectiveReadOnly = readOnly || serverReadOnly;

  const handleDisplayBeforeStartChange = (checked: boolean) => {
    setDisplayBeforeStart(checked);
    if (checked && !displayStartAt) {
      setDisplayStartAt(buildDefaultDisplayStartAt(voucherStartAt));
    }
  };

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }

    let cancelled = false;
    const loadBootstrap = async () => {
      setLoading(true);
      setError('');
      try {
        const endpoint = detailCampaignId
          ? `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/detail/shop_voucher/${detailCampaignId}`
          : `${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/create/bootstrap?voucher_type=shop_voucher`;
        const response = await fetch(endpoint, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('bootstrap failed');
        const result = (await response.json()) as VoucherCreateBootstrapResponse | VoucherDetailResponse;
        if (cancelled) return;
        setCurrency(result.meta.currency || 'RM');
        setServerReadOnly(Boolean(result.meta.read_only || detailCampaignId));
        setVoucherName(result.form.voucher_name || '');
        const nextStartAt = result.form.start_at || '';
        const nextDisplayBeforeStart = Boolean(result.form.display_before_start);
        const nextCodePrefix = result.form.code_prefix || 'HOME';
        setCodePrefix(nextCodePrefix);
        if ('voucher_code' in result) {
          setCodeSuffix(result.voucher_code.startsWith(nextCodePrefix) ? result.voucher_code.slice(nextCodePrefix.length) : result.voucher_code);
        }
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
      } catch {
        if (!cancelled) setError(detailCampaignId ? '详情页加载失败，请稍后重试。' : '创建页加载失败，请稍后重试。');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadBootstrap();
    return () => {
      cancelled = true;
    };
  }, [runId, detailCampaignId]);

  useEffect(() => {
    if (detailCampaignId || !runId || !codeSuffix.trim()) {
      setCodeCheck(null);
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setCodeChecking(true);
      try {
        const params = new URLSearchParams({ voucher_type: 'shop_voucher', code_suffix: codeSuffix.trim().toUpperCase() });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/code/check?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('code check failed');
        const result = (await response.json()) as VoucherCodeCheckResponse;
        if (!cancelled) setCodeCheck(result);
      } catch {
        if (!cancelled) setCodeCheck({ voucher_code: `${codePrefix}${codeSuffix}`, available: false, message: '代金券代码校验失败，请稍后重试。' });
      } finally {
        if (!cancelled) setCodeChecking(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [runId, codeSuffix, codePrefix, detailCampaignId]);

  const parseNumber = (value: string) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : NaN;
  };

  const validateForm = () => {
    if (effectiveReadOnly) return '当前为历史对局回溯模式，无法创建代金券。';
    if (!runId) return '当前对局不存在，无法创建代金券。';
    if (!voucherName.trim()) return '请输入代金券名称。';
    if (voucherName.trim().length > 100) return '代金券名称最多 100 个字符。';
    if (!/^[A-Z0-9]{1,5}$/.test(codeSuffix.trim().toUpperCase())) return '代金券代码后缀仅允许 A-Z、0-9，且最多 5 个字符。';
    if (codeCheck && !codeCheck.available) return codeCheck.message;
    if (!voucherStartAt || !voucherEndAt) return '请选择代金券使用期限。';
    if (voucherStartAt >= voucherEndAt) return '代金券结束时间必须晚于开始时间。';
    if (displayBeforeStart && !displayStartAt) return '请选择提前展示的时间。';
    if (displayBeforeStart && displayStartAt >= voucherStartAt) return '提前展示时间必须早于代金券开始时间。';
    const minSpend = parseNumber(minSpendAmount);
    const usage = parseNumber(usageLimit);
    const perBuyer = parseNumber(perBuyerLimit);
    if (minSpend <= 0) return '最低消费金额必须大于 0。';
    if (discountType === 'fixed_amount') {
      const amount = parseNumber(discountAmount);
      if (amount <= 0) return '优惠金额必须大于 0。';
      if (minSpend < amount) return '最低消费金额不能小于优惠金额。';
    } else {
      const percent = parseNumber(discountPercent);
      if (percent <= 0 || percent > 100) return '优惠百分比必须大于 0 且不超过 100。';
      if (maxDiscountType === 'set_amount' && parseNumber(maxDiscountAmount) <= 0) return '最大折扣金额必须大于 0。';
    }
    if (!Number.isInteger(usage) || usage <= 0) return '使用数量必须为正整数。';
    if (!Number.isInteger(perBuyer) || perBuyer <= 0 || perBuyer > usage) return '每位买家最大发放量必须为正整数，且不超过使用数量。';
    if (displayType === 'specific_channels' && !displayChannels.includes('checkout_page')) return '请选择特定展示渠道。';
    return '';
  };

  const handleSubmit = async () => {
    const validationMessage = validateForm();
    if (validationMessage) {
      setError(validationMessage);
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token || !runId) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/campaigns`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          voucher_type: 'shop_voucher',
          voucher_name: voucherName.trim(),
          code_suffix: codeSuffix.trim().toUpperCase(),
          start_at: voucherStartAt,
          end_at: voucherEndAt,
          display_before_start: displayBeforeStart,
          display_start_at: displayBeforeStart ? displayStartAt : null,
          reward_type: 'discount',
          discount_type: discountType,
          discount_amount: discountType === 'fixed_amount' ? parseNumber(discountAmount) : null,
          discount_percent: discountType === 'percent' ? parseNumber(discountPercent) : null,
          max_discount_type: discountType === 'percent' ? maxDiscountType : 'set_amount',
          max_discount_amount: discountType === 'percent' && maxDiscountType === 'set_amount' ? parseNumber(maxDiscountAmount) : null,
          min_spend_amount: parseNumber(minSpendAmount),
          usage_limit: parseNumber(usageLimit),
          per_buyer_limit: parseNumber(perBuyerLimit),
          display_type: displayType,
          display_channels: displayType === 'specific_channels' ? displayChannels : [],
        }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        throw new Error(result?.detail || '创建失败，请检查后重试。');
      }
      onBackToVouchers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败，请稍后重试。');
    } finally {
      setSaving(false);
    }
  };

  const handleCodeSuffixChange = (value: string) => {
    setCodeSuffix(value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 5));
  };

  const toggleCheckoutChannel = (checked: boolean) => {
    setDisplayChannels(checked ? ['checkout_page'] : []);
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] custom-scrollbar text-[#333] flex flex-col">
      <div className="mx-auto w-full max-w-[1440px] px-6 pt-6 pb-6 flex-1 flex flex-col relative">
        {((effectiveReadOnly && !detailCampaignId) || error || loading) && (
          <div className={`mb-4 border px-4 py-2 text-[13px] shrink-0 ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
            {error || (loading ? '正在读取游戏时间与创建规则...' : '当前为历史对局回溯模式：可浏览创建页，但无法创建代金券。')}
          </div>
        )}

        <div className="flex items-start gap-6 shrink-0 h-full">
          <div className="flex-1 min-w-[800px] flex flex-col relative">
            <div className="flex flex-col gap-4 pb-6">
              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">基础信息</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-2 text-right pr-6">代金券类型</div>
                  <div>
                    <div className="relative flex h-[40px] w-[180px] items-center justify-center rounded-sm border border-[#ee4d2d] bg-white text-[#ee4d2d] cursor-pointer">
                      <svg viewBox="0 0 21 21" className="mr-2 h-[20px] w-[20px]">
                        <path fillRule="evenodd" clipRule="evenodd" d="M14.875 5.625a2.183 2.183 0 01-2.188 2.188A2.183 2.183 0 0110.5 5.624a2.183 2.183 0 01-2.187 2.188 2.183 2.183 0 01-2.187-2.188 2.183 2.183 0 01-2.188 2.187 2.179 2.179 0 01-1.83-.99 2.174 2.174 0 01-.357-1.185v-.012l.62-2.481A2.5 2.5 0 014.796 1.25h11.408a2.5 2.5 0 012.426 1.894l.62 2.48V5.638a2.177 2.177 0 01-.357 1.186 2.18 2.18 0 01-1.83.99 2.183 2.183 0 01-2.188-2.187zM3 8.933V17.5c0 .69.56 1.25 1.25 1.25h12.5c.69 0 1.25-.56 1.25-1.25V8.933a3.44 3.44 0 01-3.125-.656 3.423 3.423 0 01-2.188.786 3.423 3.423 0 01-2.187-.786 3.424 3.424 0 01-2.188.786 3.423 3.423 0 01-2.187-.786A3.44 3.44 0 013 8.933zm8.208 6.066a.579.579 0 00-.22-.483 2.675 2.675 0 00-.768-.357 7.273 7.273 0 01-.899-.358c-.758-.371-1.137-.882-1.137-1.533a1.38 1.38 0 01.28-.856c.21-.263.488-.463.804-.579a3.121 3.121 0 011.166-.208c.388-.006.772.07 1.128.225.316.134.587.357.779.642.186.281.283.612.277.95h-1.405a.709.709 0 00-.222-.557.844.844 0 00-.589-.195.967.967 0 00-.607.168.508.508 0 00-.217.422.524.524 0 00.241.41c.262.167.548.294.847.377.346.104.68.244.996.417.632.364.949.866.949 1.506a1.43 1.43 0 01-.579 1.205c-.385.292-.914.438-1.586.438a3.186 3.186 0 01-1.289-.252 1.973 1.973 0 01-.868-.7A1.834 1.834 0 018 14.658h1.414a.91.91 0 00.241.695c.162.146.426.22.791.22a.91.91 0 00.55-.152.5.5 0 00.212-.422z" fill="#EE4D2D"></path>
                      </svg>
                      店铺代金券
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
                      请输入 A-Z, 0-9; 最多 5 个字符。<br/>
                      您的完整代金券代码为: {codeCheck?.voucher_code || `${codePrefix}${codeSuffix}`}
                      {codeSuffix ? <span className={`ml-2 ${codeCheck?.available ? 'text-green-600' : 'text-red-500'}`}>{codeChecking ? '校验中...' : codeCheck?.message}</span> : null}
                    </div>
                  </div>

                  {/* ============ 核心修改：代金券使用期限 与 提前展示 UI ============ */}
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
                          <DateTimePicker 
                            value={displayStartAt} 
                            onChange={effectiveReadOnly ? () => undefined : setDisplayStartAt}
                            inputWidthClassName="w-full" 
                            popupPlacement="bottom" 
                            maxValue={voucherStartAt || undefined} 
                          />
                          <div className="mt-2 text-[12px] text-[#999] leading-relaxed">
                            代金券开始展示后，此部分将无法再次编辑。
                          </div>
                        </div>
                      </div>
                    ) : (
                      <label className="mt-4 flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={displayBeforeStart} onChange={(e) => handleDisplayBeforeStartChange(e.target.checked)} disabled={effectiveReadOnly} className="h-[14px] w-[14px] accent-[#ee4d2d]" />
                        <span className="text-[14px] text-[#333]">提前展示代金券</span>
                      </label>
                    )}
                  </div>
                  {/* ========================================================= */}

                </div>
              </section>

              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">奖励设置</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-1 text-right pr-6">奖励类型</div>
                  <div className="flex items-center gap-6">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="rewardType" checked readOnly className="h-4 w-4 accent-[#ee4d2d]" />
                      <span>折扣</span>
                    </label>
                  </div>

                  <div className="pt-2 text-right pr-6">折扣类型 | 金额</div>
                  <div className="flex items-center gap-3 max-w-[700px]">
                    <div
                      className={`relative h-9 w-[160px] rounded-sm border ${isDropdownOpen ? 'border-[#ee4d2d]' : 'border-[#e5e5e5]'} px-3 flex items-center justify-between cursor-pointer bg-white`}
                      onClick={() => !effectiveReadOnly && setIsDropdownOpen(!isDropdownOpen)}
                    >
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

                  <div className="pt-2 text-right pr-6 flex items-center justify-end gap-1">
                    每位买家最大发放量
                    <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px]">?</span>
                  </div>
                  <div className="max-w-[700px]">
                    <input type="number" value={perBuyerLimit} onChange={(e) => setPerBuyerLimit(e.target.value)} disabled={effectiveReadOnly} className="h-9 w-[452px] rounded-sm border border-[#e5e5e5] px-3 text-[14px] outline-none focus:border-[#ee4d2d] disabled:bg-white" />
                  </div>
                </div>
              </section>

              <section className="border border-[#ececec] bg-white px-8 py-7 shadow-sm rounded-[2px]">
                <div className="text-[18px] font-medium text-[#333] mb-8">代金券展示与适用商品</div>
                <div className="grid grid-cols-[180px_1fr] items-start gap-y-6 text-[14px]">
                  <div className="pt-1 text-right pr-6">代金券展示设置</div>
                  <div className="flex flex-col gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="displayType" checked={displayType === 'all_pages'} onChange={() => setDisplayType('all_pages')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                      <span>在所有页面展示</span>
                      <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px]">?</span>
                    </label>
                    <div>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="radio" name="displayType" checked={displayType === 'specific_channels'} onChange={() => setDisplayType('specific_channels')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                        <span>特定渠道</span>
                      </label>
                      <div className="ml-6 mt-3 border border-[#e5e5e5] rounded-sm p-4 w-[240px] bg-[#fafafa]">
                        <label className="flex items-start gap-2 cursor-pointer">
                          <input type="checkbox" checked={displayChannels.includes('checkout_page')} onChange={(e) => toggleCheckoutChannel(e.target.checked)} disabled={effectiveReadOnly || displayType !== 'specific_channels'} className="h-4 w-4 mt-[2px] accent-[#ee4d2d]" />
                          <div className="flex flex-col">
                            <span>在订单支付页面展示</span>
                            <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px] mt-1">?</span>
                          </div>
                        </label>
                      </div>
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="displayType" checked={displayType === 'code_only'} onChange={() => setDisplayType('code_only')} disabled={effectiveReadOnly} className="h-4 w-4 accent-[#ee4d2d]" />
                      <span>通过代金券代码分享</span>
                      <span className="text-[#999] border border-[#999] rounded-full w-[14px] h-[14px] flex items-center justify-center text-[10px]">?</span>
                    </label>
                  </div>

                  <div className="pt-1 text-right pr-6">适用商品</div>
                  <div>
                    <div className="text-[14px] mb-1">全部商品</div>
                    <div className="text-[12px] text-[#eda500] leading-relaxed max-w-[600px]">
                      店铺代金券 V1 适用于店铺内所有可售商品。<a href="#" className="text-[#2673dd] hover:underline ml-1">了解更多</a>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            <div className="sticky bottom-0 z-50 mt-auto rounded-t-[4px] border-t border-l border-r border-[#ececec] bg-white px-8 py-3 shadow-[0_-4px_16px_rgba(0,0,0,0.04)]">
              <div className="flex items-center justify-end gap-4">
                <button type="button" onClick={onBackToVouchers} className="h-8 min-w-[80px] rounded-sm border border-[#e5e5e5] bg-white px-6 text-[14px] text-[#333] hover:bg-[#fafafa]">
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={effectiveReadOnly || loading || saving}
                  className="h-8 min-w-[80px] rounded-sm bg-[#ee4d2d] px-6 text-[14px] text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899]"
                >
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
                买家可以在店铺内的所有商品上使用此代金券。
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
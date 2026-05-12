import { useEffect, useState } from 'react';
import DateTimePicker from '../components/DateTimePicker';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface ShippingFeePromotionCreateViewProps {
  runId?: number | null;
  readOnly?: boolean;
  onBackToShippingFeePromotion: () => void;
}

interface Tier {
  id: number;
  minSpend: string;
  feeType: 'subsidize' | 'free';
  subsidizeAmount: string;
}

// 提取图标组件
const PlusIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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

export default function ShippingFeePromotionCreateView({
  runId = null,
  readOnly = false,
  onBackToShippingFeePromotion,
}: ShippingFeePromotionCreateViewProps) {
  // 基础信息状态
  const [promoName, setPromoName] = useState('');
  const [periodType, setPeriodType] = useState<'no_limit' | 'selected'>('no_limit');
  const [promoStartAt, setPromoStartAt] = useState('');
  const[promoEndAt, setPromoEndAt] = useState('');
  
  const [budgetType, setBudgetType] = useState<'no_limit' | 'selected'>('no_limit');
  const [budgetLimit, setBudgetLimit] = useState('');

  // 运费与渠道状态
  const [channels, setChannels] = useState<string[]>(['standard']);
  const [tiers, setTiers] = useState<Tier[]>([
    { id: 1, minSpend: '', feeType: 'subsidize', subsidizeAmount: '' }
  ]);

  const currency = 'RM';

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/shipping-fee-promotion/create/bootstrap`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(await response.text());
        return response.json();
      })
      .then((data) => {
        setPromoName(data.form?.promotion_name ?? '');
        setPeriodType(data.form?.period_type ?? 'no_limit');
        setPromoStartAt(data.form?.start_at ?? data.meta?.current_tick ?? '');
        setPromoEndAt(data.form?.end_at ?? data.form?.start_at ?? data.meta?.current_tick ?? '');
        setBudgetType(data.form?.budget_type ?? 'no_limit');
        setBudgetLimit(data.form?.budget_limit == null ? '' : String(data.form.budget_limit));
        setChannels(data.form?.channels?.length ? data.form.channels : ['standard']);
        setTiers((data.form?.tiers?.length ? data.form.tiers : [{ tier_index: 1, min_spend_amount: '', fee_type: 'fixed_fee', fixed_fee_amount: '' }]).map((tier: any, index: number) => ({
          id: tier.tier_index ?? index + 1,
          minSpend: tier.min_spend_amount == null ? '' : String(tier.min_spend_amount),
          feeType: tier.fee_type === 'free_shipping' ? 'free' : 'subsidize',
          subsidizeAmount: tier.fixed_fee_amount == null ? '' : String(tier.fixed_fee_amount),
        })));
      })
      .catch(() => undefined);
  }, [runId]);

  const handleSubmit = async () => {
    if (readOnly || !runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/shipping-fee-promotions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        promotion_name: promoName,
        period_type: periodType,
        start_at: promoStartAt,
        end_at: periodType === 'selected' ? promoEndAt : null,
        budget_type: budgetType,
        budget_limit: budgetType === 'selected' && budgetLimit ? Number(budgetLimit) : null,
        channels,
        tiers: tiers.map((tier, index) => ({
          tier_index: index + 1,
          min_spend_amount: Number(tier.minSpend),
          fee_type: tier.feeType === 'free' ? 'free_shipping' : 'fixed_fee',
          fixed_fee_amount: tier.feeType === 'free' ? null : Number(tier.subsidizeAmount),
        })),
      }),
    });
    if (!response.ok) {
      const errorText = await response.text();
      window.alert(errorText || '创建失败');
      return;
    }
    onBackToShippingFeePromotion();
  };

  // 处理渠道选择
  const toggleChannel = (channel: string) => {
    if (readOnly) return;
    setChannels(prev => 
      prev.includes(channel) ? prev.filter(c => c !== channel) : [...prev, channel]
    );
  };

  // 添加运费层级
  const handleAddTier = () => {
    if (readOnly || tiers.length >= 3) return;
    setTiers([...tiers, { id: Date.now(), minSpend: '', feeType: 'subsidize', subsidizeAmount: '' }]);
  };

  // 删除运费层级
  const handleRemoveTier = (idToRemove: number) => {
    if (readOnly) return;
    setTiers(tiers.filter(t => t.id !== idToRemove));
  };

  // 更新层级数据
  const updateTier = (id: number, field: keyof Tier, value: string) => {
    if (readOnly) return;
    setTiers(tiers.map(t => t.id === id ? { ...t,[field]: value } : t));
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto w-[1360px]">
        {readOnly ? (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览运费促销创建页，但无法创建或编辑活动。
          </div>
        ) : null}

        {/* ================= 基础信息 ================= */}
        <section className="mb-5 border border-[#ececec] bg-white pt-8 px-8 pb-0 shadow-sm rounded-[2px] flex gap-12">
          
          {/* 左侧表单 */}
          <div className="flex-1 flex flex-col gap-8">
            <div className="text-[18px] font-medium text-[#333] mb-2">基础信息</div>
            
            <div className="grid grid-cols-[180px_1fr] items-start gap-y-8 text-[14px]">
              
              {/* 运费促销名称 */}
              <div className="pt-2 text-right pr-6 text-[#666]">运费促销名称</div>
              <div className="max-w-[600px]">
                <div className="flex h-9 w-full items-center rounded-sm border border-[#e5e5e5] px-3 focus-within:border-[#ee4d2d]">
                  <input 
                    type="text" 
                    value={promoName}
                    onChange={(e) => setPromoName(e.target.value.slice(0, 20))}
                    disabled={readOnly}
                    className="flex-1 outline-none text-[14px] disabled:bg-white" 
                    placeholder="请输入" 
                  />
                  <span className="text-[12px] text-[#999]">{promoName.length}/20</span>
                </div>
                <div className="mt-2 text-[12px] text-[#999]">运费促销名称仅卖家可见，不向买家展示。</div>
              </div>

              {/* 运费促销期限 */}
              <div className="pt-1 text-right pr-6 text-[#666]">运费促销期限</div>
              <div className="flex flex-col gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="radio" 
                    checked={periodType === 'no_limit'} 
                    onChange={() => setPeriodType('no_limit')}
                    disabled={readOnly}
                    className="h-4 w-4 accent-[#ee4d2d]" 
                  />
                  <span>无期限</span>
                </label>
                <div className="flex flex-col gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input 
                      type="radio" 
                      checked={periodType === 'selected'} 
                      onChange={() => setPeriodType('selected')}
                      disabled={readOnly}
                      className="h-4 w-4 accent-[#ee4d2d]" 
                    />
                    <span>自定义期限</span>
                  </label>
                  {periodType === 'selected' && (
                    <div className="ml-6 flex items-center gap-3">
                      <DateTimePicker 
                        value={promoStartAt} 
                        onChange={setPromoStartAt} 
                        inputWidthClassName="w-[180px]" 
                        popupPlacement="bottom" 
                        maxValue={promoEndAt || undefined}                       />
                      <span className="text-[#999] text-[12px]">—</span>
                      <DateTimePicker 
                        value={promoEndAt} 
                        onChange={setPromoEndAt} 
                        inputWidthClassName="w-[180px]" 
                        popupPlacement="bottom" 
                        minValue={promoStartAt || undefined}                       />
                    </div>
                  )}
                </div>
              </div>

              {/* 促销预算 */}
              <div className="pt-1 text-right pr-6 text-[#666]">促销预算</div>
              <div className="flex flex-col gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="radio" 
                    checked={budgetType === 'no_limit'} 
                    onChange={() => setBudgetType('no_limit')}
                    disabled={readOnly}
                    className="h-4 w-4 accent-[#ee4d2d]" 
                  />
                  <span>无预算限制</span>
                </label>
                <div className="flex flex-col gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input 
                      type="radio" 
                      checked={budgetType === 'selected'} 
                      onChange={() => setBudgetType('selected')}
                      disabled={readOnly}
                      className="h-4 w-4 accent-[#ee4d2d]" 
                    />
                    <span>自定义预算</span>
                  </label>
                  {budgetType === 'selected' && (
                    <div className="ml-6 flex flex-col gap-2">
                      <div className="flex h-9 w-[452px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                        <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>
                        <input 
                          type="number" 
                          value={budgetLimit}
                          onChange={(e) => setBudgetLimit(e.target.value)}
                          disabled={readOnly} 
                          className="flex-1 outline-none text-[14px] px-3 disabled:bg-[#f5f5f5]" 
                          placeholder="输入" 
                        />
                      </div>
                      <div className="text-[12px] text-[#999]">当预算用尽时，促销活动将自动结束。</div>
                    </div>
                  )}
                </div>
              </div>

            </div>
          </div>

          {/* 右侧预览图 */}
          <div className="w-[320px] shrink-0 hidden md:block mt-[60px] relative md:-left-20">
            <div className="h-[480px] w-full overflow-hidden bg-contain bg-no-repeat bg-top" style={{ backgroundImage: 'url("https://deo.shopeemobile.com/shopee/shopee-seller-live-sg/mmf_portal_seller_root_dir/static/modules/shipping-promotion/image/SG@2x.a589815.png")' }}>
            </div>
          </div>

        </section>

        {/* ================= 物流渠道与运费 ================= */}
        <section className="border border-[#ececec] bg-white p-8 shadow-sm rounded-[2px]">
          <div className="text-[18px] font-medium text-[#333] mb-8">物流渠道与运费</div>
          
          <div className="grid grid-cols-[180px_1fr] items-start gap-y-8 text-[14px]">
            
            {/* 物流渠道 */}
            <div className="pt-1 text-right pr-6 text-[#666]">物流渠道</div>
            <div className="flex items-center gap-8 pt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={channels.includes('standard')} 
                  onChange={() => toggleChannel('standard')}
                  disabled={readOnly}
                  className="h-4 w-4 accent-[#ee4d2d]" 
                />
                <span>标准快递 (Standard Delivery)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={channels.includes('bulky')} 
                  onChange={() => toggleChannel('bulky')}
                  disabled={readOnly}
                  className="h-4 w-4 accent-[#ee4d2d]" 
                />
                <span>大件快递 (Standard Delivery Bulky)</span>
              </label>
            </div>

            {/* 运费设置 */}
            <div className="pt-2 text-right pr-6 text-[#666]">运费设置</div>
            <div className="max-w-[760px]">
              <div className="text-[12px] text-[#999] leading-relaxed mb-4">
                · 最多可设置 3 个层级的最低消费运费折扣。<br/>
                · 最低消费金额越高，运费折扣应当越大。
              </div>

              {/* 层级表格 */}
              <div className="border border-[#e5e5e5] rounded-sm">
                
                {/* 表头 */}
                <div className="grid grid-cols-[60px_1.2fr_1.8fr_80px] bg-[#fafafa] px-4 py-3 text-[13px] text-[#666] border-b border-[#e5e5e5]">
                  <div className="text-center">层级</div>
                  <div>最低消费金额</div>
                  <div>运费</div>
                  <div className="text-center">操作</div>
                </div>

                {/* 表格行 */}
                {tiers.map((tier, index) => (
                  <div key={tier.id} className="grid grid-cols-[60px_1.2fr_1.8fr_80px] px-4 py-5 border-b border-[#e5e5e5] last:border-b-0 items-start">
                    
                    <div className="text-center pt-2 text-[#333] font-medium">{index + 1}</div>
                    
                    <div className="pr-4">
                      <div className="flex h-9 w-[180px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                        <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>
                        <input 
                          type="number" 
                          value={tier.minSpend}
                          onChange={(e) => updateTier(tier.id, 'minSpend', e.target.value)}
                          disabled={readOnly}
                          className="flex-1 outline-none text-[14px] px-3 disabled:bg-[#f5f5f5]" 
                          placeholder="输入"
                        />
                      </div>
                    </div>
                    
                    <div className="flex flex-col gap-4 pt-1">
                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 cursor-pointer w-[90px]">
                          <input 
                            type="radio" 
                            name={`feeType-${tier.id}`} 
                            checked={tier.feeType === 'subsidize'} 
                            onChange={() => updateTier(tier.id, 'feeType', 'subsidize')}
                            disabled={readOnly}
                            className="h-4 w-4 accent-[#ee4d2d]" 
                          />
                          <span>运费减免</span>
                        </label>
                        {tier.feeType === 'subsidize' && (
                          <div className="flex h-9 w-[150px] items-center rounded-sm border border-[#e5e5e5] focus-within:border-[#ee4d2d] overflow-hidden">
                            <div className="bg-[#f5f5f5] px-3 h-full flex items-center border-r border-[#e5e5e5] text-[#999]">{currency}</div>
                            <input 
                              type="number" 
                              value={tier.subsidizeAmount}
                              onChange={(e) => updateTier(tier.id, 'subsidizeAmount', e.target.value)}
                              disabled={readOnly}
                              className="flex-1 outline-none text-[14px] px-3 disabled:bg-[#f5f5f5]" 
                              placeholder="输入"
                            />
                          </div>
                        )}
                      </div>

                      <label className="flex items-center gap-2 cursor-pointer w-[90px]">
                        <input 
                          type="radio" 
                          name={`feeType-${tier.id}`} 
                          checked={tier.feeType === 'free'} 
                          onChange={() => updateTier(tier.id, 'feeType', 'free')}
                          disabled={readOnly}
                          className="h-4 w-4 accent-[#ee4d2d]" 
                        />
                        <span>免运费</span>
                      </label>
                    </div>

                    <div className="flex justify-center pt-1.5">
                      {index > 0 && !readOnly && (
                        <button 
                          type="button" 
                          onClick={() => handleRemoveTier(tier.id)}
                          className="text-[#999] hover:text-[#ee4d2d] transition-colors p-1"
                          title="删除层级"
                        >
                          <TrashIcon />
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {/* 添加层级按钮 */}
                {!readOnly && tiers.length < 3 && (
                  <div className="px-4 py-4 border-t border-[#e5e5e5] bg-[#fafafa]">
                    <button 
                      type="button" 
                      onClick={handleAddTier}
                      className="flex items-center gap-1.5 text-[14px] text-[#2673dd] hover:text-[#1e5eb3] transition-colors font-medium"
                    >
                      <PlusIcon />
                      添加层级
                    </button>
                  </div>
                )}
              </div>

            </div>
          </div>
        </section>

        {/* 底部操作按钮 */}
        <div className="mt-5 flex justify-end gap-3 pb-8">
          <button
            type="button"
            onClick={onBackToShippingFeePromotion}
            className="h-8 min-w-[80px] rounded-sm border border-[#e5e5e5] bg-white px-6 text-[14px] text-[#333] hover:bg-[#fafafa]"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={readOnly}
            className="h-8 min-w-[80px] rounded-sm bg-[#ee4d2d] px-6 text-[14px] text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899]"
          >
            确认
          </button>
        </div>
      </div>
    </div>
  );
}
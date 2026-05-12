import { useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface ShippingFeePromotionViewProps {
  runId?: number | null;
  readOnly?: boolean;
  onCreate: () => void;
}

interface ShippingFeePromotionRow {
  id: number;
  promotion_name: string;
  channels_text: string;
  tier_summary: string;
  budget_text: string;
  budget_used_text: string;
  status: string;
  status_label: string;
  period: string;
}

interface ShippingFeePromotionListResponse {
  tabs: Array<{ key: string; status: string; count: number }>;
  list: {
    page: number;
    page_size: number;
    total: number;
    items: ShippingFeePromotionRow[];
  };
}

export default function ShippingFeePromotionView({ runId = null, readOnly = false, onCreate }: ShippingFeePromotionViewProps) {
  const [activeStatus, setActiveStatus] = useState('all');
  const [promotionData, setPromotionData] = useState<ShippingFeePromotionListResponse | null>(null);

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    const query = new URLSearchParams({ status: activeStatus, page: '1', page_size: '10' });
    fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/shipping-fee-promotions?${query.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(await response.text());
        return response.json();
      })
      .then((data: ShippingFeePromotionListResponse) => setPromotionData(data))
      .catch(() => setPromotionData({ tabs: [], list: { page: 1, page_size: 10, total: 0, items: [] } }));
  }, [activeStatus, runId]);

  const mockPromotions = promotionData?.list.items ?? [];
  const tabs = promotionData?.tabs?.length
    ? promotionData.tabs
    : [
        { key: '全部', status: 'all', count: 0 },
        { key: '进行中', status: 'ongoing', count: 0 },
        { key: '即将开始', status: 'upcoming', count: 0 },
        { key: '已结束', status: 'ended', count: 0 },
      ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333] font-sans">
      <div className="mx-auto w-full max-w-[1660px]">
        {/* 全局提示（回溯模式） */}
        {readOnly && (
          <div className="mb-4 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700 shrink-0">
            当前为历史对局回溯模式：可浏览运费促销页，但无法创建或编辑活动。
          </div>
        )}

        {/* 主体白色卡片 */}
        <div className="bg-white shadow-sm rounded-[2px] min-h-[600px] border border-[#ececec]">
          
          {/* 1. 顶部标题、说明及右侧操作区 */}
          <div className="px-8 pt-8 pb-6 flex justify-between items-start">
            <div>
              <h1 className="text-[20px] font-medium text-[#333]">促销列表</h1>
              <p className="mt-2 text-[14px] text-[#999]">
                通过设置运费促销，您的店铺可以吸引更多买家！ <a href="#" className="text-[#2673dd] hover:underline">了解更多</a>
              </p>
            </div>

            {/* 右侧按钮组 */}
            <div className="flex flex-col items-end gap-3">
              <button
                type="button"
                onClick={onCreate}
                disabled={readOnly}
                className="h-9 px-6 rounded-sm bg-[#ee4d2d] text-[14px] text-white hover:bg-[#d83f21] disabled:cursor-not-allowed disabled:bg-[#f3a899] flex items-center shadow-sm"
              >
                <span className="text-lg mr-1 font-light leading-none">+</span> 创建
              </button>
            </div>
          </div>

          {/* 2. 标签页 (Tabs) */}
          <div className="flex items-center gap-10 border-b border-[#efefef] px-8 text-[15px]">
            {tabs.map((tab) => (
              <button
                key={tab.status}
                type="button"
                onClick={() => setActiveStatus(tab.status)}
                className={`border-b-[2px] pb-4 px-1 -mb-[1px] transition-colors ${
                  activeStatus === tab.status
                    ? 'border-[#ee4d2d] font-medium text-[#ee4d2d]'
                    : 'border-transparent text-[#333] hover:text-[#ee4d2d]'
                }`}
              >
                {tab.key}
              </button>
            ))}
          </div>

          {/* 3. 列表区域 或 缺省空状态 */}
          {mockPromotions.length > 0 ? (
            /* 表格视图 */
            <div className="px-8 py-6">
              {/* 【改动点】：增加了一个带有 border 的容器，显式画出表格的上下左右四周边框 */}
              <div className="border border-[#e5e5e5] rounded-[2px] overflow-hidden">
                <table className="w-full text-left text-[14px]">
                  {/* 【改动点】：原本的 border-y 改为 border-b，因为顶部边框已经由外层容器提供了 */}
                  <thead className="bg-[#fafafa] border-b border-[#e5e5e5] text-[#999]">
                    <tr>
                      <th className="py-3 px-4 font-normal w-[15%]">运费促销名称</th>
                      <th className="py-3 px-4 font-normal w-[20%]">物流渠道</th>
                      <th className="py-3 px-4 font-normal w-[20%]">运费设置</th>
                      <th className="py-3 px-4 font-normal w-[15%]">预算</th>
                      <th className="py-3 px-4 font-normal w-[10%]">状态</th>
                      <th className="py-3 px-4 font-normal w-[12%]">活动时间</th>
                      <th className="py-3 px-4 font-normal w-[8%] text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mockPromotions.map((promo) => (
                      <tr 
                        key={promo.id} 
                        // 【改动点】：加入了 last:border-b-0，防止最后一行数据的底部边框和外层容器的底部边框出现“双粗线”
                        className="border-b border-[#e5e5e5] last:border-b-0 hover:bg-[#fafafa] transition-colors"
                      >
                        <td className="py-4 px-4 align-top text-[#333]">{promo.promotion_name}</td>
                        <td className="py-4 px-4 align-top">
                          <div className="flex items-center text-[#333]">
                            <div className="w-[18px] h-[18px] rounded-full bg-[#ee4d2d] text-white flex items-center justify-center text-[12px] font-bold mr-2 shrink-0">
                              S
                            </div>
                            {promo.channels_text}
                          </div>
                        </td>
                        <td className="py-4 px-4 align-top text-[#333]">{promo.tier_summary}</td>
                        <td className="py-4 px-4 align-top text-[#333]">
                          <div>总预算: {promo.budget_text}</div>
                          <div className="text-[#999] mt-0.5">已使用: {promo.budget_used_text}</div>
                        </td>
                        <td className="py-4 px-4 align-top">
                          <span className="text-[#00bfa5] border border-[#00bfa5] bg-[#e6f9f6] px-1.5 py-0.5 rounded text-[12px]">
                            {promo.status_label}
                          </span>
                        </td>
                        <td className="py-4 px-4 align-top text-[#333]">{promo.period}</td>
                        <td className="py-4 px-4 align-top text-right">
                          <div className="flex flex-col items-end gap-2 text-[#2673dd]">
                            <button className="hover:underline">编辑</button>
                            <button className="hover:underline">结束</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            /* 缺省空状态 (Empty State) */
            <div className="flex flex-col items-center justify-center pt-24 pb-32">
              <div className="relative mb-6">
                <svg
                  width="100"
                  height="100"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#e2e2e2"
                  strokeWidth="1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ transform: 'rotate(-10deg)' }}
                >
                  <path d="m3 11 18-5v12L3 14v-3z" />
                  <path d="M11.6 16.8a3 3 0 1 1-5.8-1.6" />
                </svg>
                <div className="absolute top-[5px] right-[-5px] h-[7px] w-[7px] rounded-full border border-[#e2e2e2]" />
                <div className="absolute top-[20px] right-[-15px] h-[5px] w-[5px] rounded-full border border-[#e2e2e2]" />
              </div>
              
              <div className="text-[14px] text-[#999] mb-8">
                暂无运费促销活动
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
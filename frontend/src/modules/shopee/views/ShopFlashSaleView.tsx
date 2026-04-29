import { useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface ShopFlashSaleViewProps {
  runId: number | null;
  readOnly?: boolean;
  onCreate?: () => void;
}

interface FlashSaleCampaignRow {
  id: number;
  display_time: string;
  product_enabled_count: number;
  product_limit: number;
  reminder_count: number;
  click_count: number;
  status_label: string;
  enabled: boolean;
}

interface FlashSaleTableRow {
  time: string;
  enabledCount: number;
  totalCount: number;
  reminders: string | number;
  clicks: string | number;
  status: string;
  enabled?: boolean;
  isNextDay?: boolean;
}

export default function ShopFlashSaleView({ runId, readOnly = false, onCreate }: ShopFlashSaleViewProps) {
  const [activeTab, setActiveTab] = useState('全部');
  const [campaignRows, setCampaignRows] = useState<FlashSaleCampaignRow[]>([]);

  useEffect(() => {
    if (!runId) return;
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) return;
    const statusMap: Record<string, string> = { 全部: 'all', 进行中: 'ongoing', 即将开始: 'upcoming', 已结束: 'ended' };
    let cancelled = false;
    const loadRows = async () => {
      const params = new URLSearchParams({ status: statusMap[activeTab] || 'all', page: '1', page_size: '20' });
      const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/campaigns?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;
      const result = await response.json();
      if (!cancelled) setCampaignRows(result.rows || []);
    };
    void loadRows();
    return () => {
      cancelled = true;
    };
  }, [activeTab, runId]);

  // 模拟截图中的表格数据
  const mockTableData: FlashSaleTableRow[] = campaignRows.length > 0 ? campaignRows.map((row) => ({
    time: row.display_time,
    enabledCount: row.product_enabled_count,
    totalCount: row.product_limit,
    reminders: row.reminder_count || '-',
    clicks: row.click_count || '-',
    status: row.status_label,
    enabled: row.enabled,
  })) : [
    {
      time: '19-03-2026 18:00 - 21:00',
      enabledCount: 0,
      totalCount: 50,
      reminders: '-',
      clicks: '-',
      status: '已结束',
    },
    {
      time: '19-03-2026 12:00 - 18:00',
      enabledCount: 0,
      totalCount: 50,
      reminders: '-',
      clicks: '-',
      status: '已结束',
    },
    {
      time: '19-03-2026 00:00 - 12:00',
      enabledCount: 0,
      totalCount: 50,
      reminders: '-',
      clicks: '-',
      status: '已结束',
    },
    {
      time: '18-03-2026 21:00 - 00:00',
      isNextDay: true, // +1 标识
      enabledCount: 0,
      totalCount: 50,
      reminders: '-',
      clicks: '-',
      status: '已结束',
    },
    {
      time: '18-03-2026 12:00 - 18:00',
      enabledCount: 0,
      totalCount: 50,
      reminders: '-',
      clicks: '-',
      status: '已结束',
    },
  ];

  // 问号提示小图标组件
  const InfoIcon = () => (
    <svg viewBox="0 0 1024 1024" className="inline-block w-3.5 h-3.5 ml-1 text-[#b2b2b2] fill-current" >
      <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path>
      <path d="M464 688h96v-96h-96v96zm48-392c-65.3 0-118.3 49.3-126.9 113.1l74 15.6c4.5-33.6 34.3-56.7 60.9-56.7 34.1 0 64 25.1 64 60 0 25.5-16.7 44.5-44.1 61.2l-23.9 14.6V560h80v-34.5l22.4-13.6c39-23.7 61.6-58.1 61.6-99.9 0-64-57.3-116-128-116z"></path>
    </svg>
  );

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto max-w-[1660px]">
        
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览我的店铺限时抢购页，但无法创建或编辑活动。
          </div>
        )}

        {/* 1. 表现数据面板 (Performance Section) */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-6">
          <div className="px-6 py-4 flex justify-between items-center border-b border-[#ebebeb]">
            <div className="flex items-center gap-3">
              <h2 className="text-[16px] font-medium text-[#333]">我的店铺限时抢购表现</h2>
              <span className="text-[12px] text-[#999]">(数据截至于 22-04-2026 至 29-04-2026 GMT+7)</span>
            </div>
            <button className="text-[14px] text-[#05a] hover:underline">更多 &gt;</button>
          </div>
          
          <div className="grid grid-cols-4 py-6">
            <div className="px-6 border-r border-[#ebebeb]">
              <div className="text-[14px] text-[#666]">销售额 <InfoIcon /></div>
              <div className="mt-2 text-[24px] text-[#333]">฿ 0</div>
              <div className="mt-1 text-[12px] text-[#999]">较前7天 <span className="text-[#333]">0.00%</span></div>
            </div>
            <div className="px-6 border-r border-[#ebebeb]">
              <div className="text-[14px] text-[#666]">订单 <InfoIcon /></div>
              <div className="mt-2 text-[24px] text-[#333]">0</div>
              <div className="mt-1 text-[12px] text-[#999]">较前7天 <span className="text-[#333]">0.00%</span></div>
            </div>
            <div className="px-6 border-r border-[#ebebeb]">
              <div className="text-[14px] text-[#666]">买家数 <InfoIcon /></div>
              <div className="mt-2 text-[24px] text-[#333]">0</div>
              <div className="mt-1 text-[12px] text-[#999]">较前7天 <span className="text-[#333]">0.00%</span></div>
            </div>
            <div className="px-6">
              <div className="text-[14px] text-[#666]">点击率 (CTR) <InfoIcon /></div>
              <div className="mt-2 text-[24px] text-[#333]">0.00 %</div>
              <div className="mt-1 text-[12px] text-[#999]">较前7天 <span className="text-[#333]">-%</span></div>
            </div>
          </div>
        </section>

        {/* 2. 活动列表面板 (Promotion List Section) */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb]">
          {/* Header */}
          <div className="px-6 pt-6 pb-4 flex justify-between items-start">
            <div>
              <h2 className="text-[18px] font-medium text-[#333]">活动列表</h2>
              <p className="text-[13px] text-[#999] mt-1">
                在您的店铺页面开展限时抢购活动，提升销量！ <a href="#" className="text-[#05a] hover:underline">了解更多</a>
              </p>
            </div>
            <button
              type="button"
              onClick={onCreate}
              disabled={readOnly}
              className="bg-[#ee4d2d] text-white px-5 py-2 rounded-[2px] text-[14px] flex items-center gap-1 hover:bg-[#d73f22] transition-colors disabled:cursor-not-allowed disabled:bg-[#f3a899]"
            >
              <span className="text-lg leading-none mb-[2px]">+</span> 创建
            </button>
          </div>

          {/* Tabs */}
          <div className="flex px-6 border-b border-[#ebebeb] text-[14px]">
            {['全部', '进行中', '即将开始', '已结束'].map((tab) => (
              <div
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`mr-8 pb-3 cursor-pointer relative ${
                  activeTab === tab ? 'text-[#ee4d2d] font-medium' : 'text-[#333] hover:text-[#ee4d2d]'
                }`}
              >
                {tab}
                {activeTab === tab && (
                  <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#ee4d2d]"></div>
                )}
              </div>
            ))}
          </div>

          {/* Filter Toolbar */}
          <div className="px-6 py-4 flex items-center gap-4 text-[14px]">
            <span className="text-[#333]">时间段</span>
            <div className="relative">
              {/* 日期选择器 mock */}
              <div className="flex items-center border border-[#e5e5e5] rounded-[2px] px-3 py-1.5 w-[260px] text-[#999] bg-white cursor-pointer hover:border-[#ccc]">
                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd"></path></svg>
                请选择日期范围
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="px-6 pb-6">
            <div className="w-full border border-[#ebebeb] rounded-sm">
              {/* Table Header */}
              <div className="grid grid-cols-[1.8fr_1.5fr_1.2fr_1.2fr_1fr_0.8fr_1fr] bg-[#fafafa] border-b border-[#ebebeb] px-4 py-3 text-[13px] text-[#999] font-medium">
                <div>时间段</div>
                <div>商品</div>
                <div>提醒设置数</div>
                <div>商品点击数</div>
                <div>状态</div>
                <div>启用/停用</div>
                <div>操作</div>
              </div>

              {/* Table Body */}
              <div className="text-[13px] text-[#333]">
                {mockTableData.map((row, index) => (
                  <div key={index} className="grid grid-cols-[1.8fr_1.5fr_1.2fr_1.2fr_1fr_0.8fr_1fr] border-b border-[#ebebeb] px-4 py-4 items-start hover:bg-[#fcfcfc] transition-colors last:border-0">
                    
                    {/* 时间段 */}
                    <div className="pr-4 leading-relaxed font-medium">
                      {row.time}
                      {row.isNextDay && <sup className="text-[#999] ml-0.5 text-[10px]">+1</sup>}
                    </div>
                    
                    {/* 商品 */}
                    <div className="pr-4 leading-relaxed text-[#666]">
                      限时抢购可用 <span className="text-[#ee4d2d]">{row.enabledCount}</span><br />
                      总可用 {row.totalCount}
                    </div>
                    
                    {/* 提醒 / 点击 */}
                    <div>{row.reminders}</div>
                    <div>{row.clicks}</div>
                    
                    {/* 状态 */}
                    <div>
                      <span className="bg-[#f5f5f5] text-[#999] px-2 py-1 rounded-sm text-[12px]">{row.status}</span>
                    </div>
                    
                    {/* 启用/停用 Toggle (Mock) */}
                    <div>
                      <div className="w-9 h-5 bg-[#c6e9d0] rounded-full relative cursor-not-allowed opacity-80">
                         <div className="w-4 h-4 bg-white rounded-full absolute right-0.5 top-0.5 shadow-sm"></div>
                      </div>
                    </div>
                    
                    {/* 操作 */}
                    <div className="flex flex-col gap-1.5 items-start">
                      <button className="text-[#05a] hover:underline">详情</button>
                      <button className="text-[#05a] hover:underline">复制</button>
                      <button className="text-[#05a] hover:underline">数据</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Pagination (Mock) */}
            <div className="flex items-center justify-end mt-5 text-[13px] text-[#666] gap-2">
              <button className="p-1 text-[#ccc]" disabled>&lt;</button>
              <button className="px-2 text-[#ee4d2d]">1</button>
              <button className="px-2 hover:text-[#ee4d2d]">2</button>
              <button className="px-2 hover:text-[#ee4d2d]">3</button>
              <button className="px-2 hover:text-[#ee4d2d]">4</button>
              <button className="px-2 hover:text-[#ee4d2d]">5</button>
              <span>...</span>
              <button className="px-2 hover:text-[#ee4d2d]">193</button>
              <button className="p-1 hover:text-[#ee4d2d]">&gt;</button>
              <div className="flex items-center ml-2">
                <span className="mr-2">跳转至 页</span>
                <input type="text" className="border border-[#e5e5e5] w-12 h-7 text-center rounded-sm outline-none focus:border-[#ccc]" />
                <button className="ml-2 border border-[#e5e5e5] px-3 h-7 rounded-sm hover:bg-[#fafafa]">Go</button>
              </div>
            </div>

          </div>
        </section>
      </div>
    </div>
  );
}
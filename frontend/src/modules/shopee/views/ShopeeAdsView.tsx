import React, { useState } from 'react';

interface ShopeeAdsViewProps {
  readOnly?: boolean;
}

// ---------------- 常用图标组件 ----------------
const InfoIcon = () => (
  <svg viewBox="0 0 1024 1024" className="inline-block w-3.5 h-3.5 ml-1 text-[#b2b2b2] fill-current cursor-pointer hover:text-[#ee4d2d] transition-colors">
    <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path>
    <path d="M464 688h96v-96h-96v96zm48-392c-65.3 0-118.3 49.3-126.9 113.1l74 15.6c4.5-33.6 34.3-56.7 60.9-56.7 34.1 0 64 25.1 64 60 0 25.5-16.7 44.5-44.1 61.2l-23.9 14.6V560h80v-34.5l22.4-13.6c39-23.7 61.6-58.1 61.6-99.9 0-64-57.3-116-128-116z"></path>
  </svg>
);

const CheckCircleIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="#26b562" className="mr-1.5 inline-block">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="#fff"></path>
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M10 17.41L4.59 12 6 10.59l4 4 8-8L19.41 8 10 17.41z" fill="#fff"></path>
  </svg>
);

const WarningIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="#ffb537" className="inline-block flex-shrink-0">
    <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"></path>
  </svg>
);

const SortIcon = () => (
  <div className="inline-flex flex-col ml-1 w-2 cursor-pointer opacity-40 hover:opacity-100">
    <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="3" fill="none" className="-mb-[3px]"><polyline points="18 15 12 9 6 15"></polyline></svg>
    <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="3" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
  </div>
);

const ChevronDownIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>;
const ChevronRightIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><polyline points="9 18 15 12 9 6"></polyline></svg>;
const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="mr-1">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    <polyline points="9 12 11 14 15 10"></polyline>
  </svg>
);
export default function ShopeeAdsView({ readOnly = false }: ShopeeAdsViewProps) {
  const [activeTab, setActiveTab] = useState('全部点击出价广告');
  const [listTab, setListTab] = useState('全部');

  // 广告表现数据
  const performanceMetrics =[
    { label: '曝光量', value: '0', color: 'border-t-[#e5e5e5]' },
    { label: '点击数', value: '0', color: 'border-t-[#ffb537]' },
    { label: '点击率 (CTR)', value: '0.00%', color: 'border-t-[#e5e5e5]' },
    { label: '订单数', value: '0', color: 'border-t-[#e5e5e5]' },
    { label: '售出商品数', value: '0', color: 'border-t-[#e5e5e5]' },
    { label: '销售额', value: 'RM 0.00', color: 'border-t-[#f37021]' },
    { label: '花费', value: 'RM 0.00', color: 'border-t-[#9d54e0]' },
    { label: '投入产出比 (ROAS)', value: '0.00', color: 'border-t-[#e5e5e5]' },
  ];

  // 广告列表模拟数据
  const adsList =[
    {
      id: 'A001',
      image: 'https://via.placeholder.com/48/f5f5f5/ff7337?text=Shop',
      name: '店铺广告 04-12-2024',
      type: '店铺广告 - 自动出价',
      period: '19/12/2024 - 23/12/2024',
      status: 'Ended',
      statusLabel: '已结束',
      hasWarning: false,
      roasProtected: false,
      budget: 'RM 100.00',
      targetRoas: '-',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
    },
    {
      id: 'A002',
      image: 'https://via.placeholder.com/48',
      name: '电竞电脑桌 加固加厚 坚固耐用...',
      type: '商品广告 - GMV Max 自定义 ROAS',
      period: '无结束日期',
      status: 'Paused',
      statusLabel: '暂停中',
      hasWarning: true,
      roasProtected: true,
      budget: 'RM 300.00',
      targetRoas: '8.4',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
    },
    {
      id: 'A003',
      image: 'https://via.placeholder.com/48',
      name: '厨房收纳置物架 多层碗碟沥水架...',
      type: '商品广告 - GMV Max 自定义 ROAS',
      period: '无结束日期',
      status: 'Paused',
      statusLabel: '暂停中',
      hasWarning: true,
      roasProtected: true,
      budget: 'RM 500.00',
      targetRoas: '8.4',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
    },
    {
      id: 'A004',
      image: 'https://via.placeholder.com/48',
      name: 'HomeNeat 厨房收纳架 不锈钢 2-3层...',
      type: '商品广告 - GMV Max 自动出价',
      period: '无结束日期',
      status: 'Paused',
      statusLabel: '暂停中',
      hasWarning: true,
      roasProtected: false,
      budget: 'RM 1,200.00',
      targetRoas: '6.51 ~ 10.51',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
    }
  ];

  const tableGridCols = "grid-cols-[40px_minmax(320px,3.5fr)_1fr_1fr_1fr_1fr_1fr_1fr_1fr_1fr]";

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto max-w-[1660px]">
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览 Shopee 广告页，但无法创建或编辑广告。
          </div>
        )}

        {/* 顶部 Header */}
        <div className="bg-white px-6 py-4 flex items-center justify-between shadow-sm border border-[#ebebeb] rounded-sm mb-4">
          <div className="flex items-center gap-4">
            <h1 className="text-[20px] font-medium text-[#333]">Shopee 广告</h1>
            <span className="flex items-center gap-1.5 text-[13px] text-[#05a] cursor-pointer hover:underline font-medium border-l border-[#e5e5e5] pl-4">
            </span>
          </div>
          <button 
            disabled={readOnly}
            className="bg-[#ee4d2d] text-white px-6 py-2 rounded-sm text-[14px] hover:bg-[#d83f21] transition-colors disabled:bg-[#f3a899] disabled:cursor-not-allowed"
          >
            + 创建新广告
          </button>
        </div>

        {/* 1. 账户总览三大卡片 */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          
          {/* Card 1: 我的账户 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[16px] font-medium text-[#333]">我的账户</h2>
                <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">更多 <ChevronRightIcon /></span>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div>
                  <div className="text-[13px] text-[#666]">广告余额 <InfoIcon /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 73.63</div>
                </div>
                <div>
                  <div className="text-[13px] text-[#666]">今日花费 <InfoIcon /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
              </div>
              <button className="w-full bg-[#ee4d2d] text-white py-2 rounded-sm text-[14px] hover:bg-[#d83f21] transition-colors mb-4">充值</button>
            </div>
            <div className="space-y-2">
              <div className="bg-[#fafafa] border border-[#ebebeb] rounded-sm px-3 py-2 flex items-center justify-between cursor-pointer hover:border-[#ccc]">
                <div className="flex items-center gap-2 text-[13px] text-[#333]">
                  <span className="text-[#ee4d2d]">🔄</span> 开启自动充值 (卖家余额) <span className="text-[#ee4d2d] text-[11px] bg-[#fff6f4] px-1 py-0.5 rounded-sm">Sales + up to 20% ↗</span>
                </div>
                <ChevronRightIcon />
              </div>
              <div className="bg-[#fafafa] border border-[#ebebeb] rounded-sm px-3 py-2 flex items-center justify-between cursor-pointer hover:border-[#ccc]">
                <div className="flex items-center gap-2 text-[13px] text-[#333]">
                  <span className="text-[#ee4d2d]">💳</span> 自动充值 (我的余额) <span className="text-[#ee4d2d] text-[11px] bg-[#fff6f4] px-1 py-0.5 rounded-sm">保持激活</span>
                </div>
                <ChevronRightIcon />
              </div>
            </div>
          </div>

          {/* Card 2: 智能代金券 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 flex flex-col justify-between relative">
            {/* 红色角标 */}
            <div className="absolute top-0 left-0 bg-[#ee4d2d] text-white text-[12px] px-2 py-0.5 rounded-br-sm rounded-tl-sm font-medium">
              100% 平台赞助
            </div>
            
            <div>
              <div className="flex items-center justify-between mb-4 mt-2">
                <h2 className="text-[16px] font-medium text-[#333]">智能代金券</h2>
                <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">设置 <ChevronRightIcon /></span>
              </div>
              <div className="grid grid-cols-2 border border-[#ebebeb] rounded-sm py-5 px-4 my-2">
                <div className="border-r border-[#ebebeb]">
                  <div className="text-[13px] text-[#666]">代金券金额 <InfoIcon /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
                <div className="pl-6">
                  <div className="text-[13px] text-[#666]">代金券促成销售额 <InfoIcon /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
              </div>
            </div>
            <div className="bg-[#f0faef] text-[#00bfa5] text-[13px] px-3 py-2 rounded-sm mt-6 flex items-center">
              <CheckCircleIcon /> 通过平台赞助代金券提升广告效果
            </div>
          </div>

          {/* Card 3: ROAS 保护 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[16px] font-medium text-[#333]">ROAS 保护</h2>
                <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">了解更多</span>
              </div>
              <div className="grid grid-cols-2 border border-[#ebebeb] rounded-sm py-5 px-4 my-2">
                <div className="border-r border-[#ebebeb]">
                  <div className="text-[13px] text-[#666]">过去7天返点 <InfoIcon /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
                <div className="pl-6">
                  <div className="text-[13px] text-[#666]">受 ROAS 保护的广告 <InfoIcon /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">0</div>
                </div>
              </div>
            </div>
            <div className="bg-[#f0faef] text-[#00bfa5] text-[13px] px-3 py-2 rounded-sm mt-6 flex items-center">
              <CheckCircleIcon /> 使用免费广告余额补齐 ROAS 差距
            </div>
          </div>

        </div>

        {/* 2. 推荐与广告奖励 */}
        <div className="grid grid-cols-[2fr_1fr] gap-4 mb-6">
          
          {/* 推荐区域 (带假装轮播的布局) */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[16px] font-medium text-[#333]">推荐</h2>
              <div className="text-[13px] text-[#666]">
                11 个活跃项目 | <span className="text-[#05a] cursor-pointer hover:underline ml-1">查看全部 <ChevronRightIcon className="inline" /></span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 relative">
              
              {/* 推荐卡片 1 */}
              <div className="border border-[#ebebeb] rounded-sm p-4 bg-gradient-to-br from-white to-[#fff6f4] relative overflow-hidden">
                <div className="flex items-start gap-2 relative z-10">
                  <div className="mt-0.5"><WarningIcon /></div>
                  <div>
                    <h3 className="text-[14px] font-bold text-[#333] leading-snug">余额即将耗尽！开启自动充值以防止广告中断。</h3>
                    <p className="text-[13px] text-[#666] mt-2">您的余额将在几天内耗尽。开启自动充值以避免中断。</p>
                  </div>
                </div>
                <div className="mt-8 flex justify-end gap-3 relative z-10">
                  <button className="border border-[#d9d9d9] bg-white px-4 py-1.5 rounded-sm text-[13px] text-[#333] hover:bg-[#fafafa]">立即充值</button>
                  <button className="border border-[#ee4d2d] text-[#ee4d2d] bg-white px-4 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4]">开启自动充值</button>
                </div>
                {/* 装饰大三角形背景 */}
                <div className="absolute right-[-20px] bottom-[-20px] w-32 h-32 bg-[#ffedea] transform rotate-45 z-0"></div>
              </div>

              {/* 推荐卡片 2 */}
              <div className="border border-[#ebebeb] rounded-sm p-4 bg-gradient-to-br from-white to-[#fff6f4] relative overflow-hidden">
                <div className="flex items-start gap-2 relative z-10">
                  <div className="mt-0.5 text-[#ee4d2d] bg-[#ffedea] w-4 h-4 rounded-sm flex items-center justify-center text-[10px]">✓</div>
                  <div className="w-full">
                    <h3 className="text-[14px] font-bold text-[#333] leading-snug">开启自动充值 (卖家余额) 以解锁更多代金券并提升销量达 +20%</h3>
                    <div className="mt-3 bg-white/60 p-2 rounded-sm text-[12px] border border-white/40">
                      <div className="flex justify-between mb-1 text-[#666]"><span>自动充值 (卖家余额) 费率</span><span className="font-medium text-[#333]">1% <InfoIcon /></span></div>
                      <div className="flex justify-between text-[#666]"><span>预估 7 天充值金额</span><span className="font-medium text-[#333]">-</span></div>
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex justify-end gap-3 relative z-10">
                  <button className="border border-[#d9d9d9] bg-white px-4 py-1.5 rounded-sm text-[13px] text-[#333] hover:bg-[#fafafa]">自定义设置</button>
                  <button className="border border-[#ee4d2d] text-[#ee4d2d] bg-white px-4 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4]">应用设置</button>
                </div>
              </div>
              
              {/* 轮播右侧阴影箭头 */}
              <div className="absolute right-[-12px] top-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.15)] flex items-center justify-center cursor-pointer z-20">
                <ChevronRightIcon />
              </div>
            </div>
          </div>

          {/* 广告奖励 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[16px] font-medium text-[#333]">广告奖励</h2>
              <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">更多 <ChevronRightIcon /></span>
            </div>
            <div className="border border-[#ebebeb] rounded-sm p-4 relative overflow-hidden h-[155px] flex flex-col justify-between">
              <div>
                <h3 className="text-[14px] font-medium text-[#333]">充值 RM 100 广告余额</h3>
                <div className="flex items-center gap-1.5 mt-2">
                  <div className="w-4 h-4 rounded-full bg-[#ee4d2d] text-white flex items-center justify-center text-[10px] font-bold">$</div>
                  <span className="text-[13px] text-[#666]">获得 <span className="text-[#ee4d2d] font-medium">RM 40</span> 免费广告余额</span>
                </div>
              </div>
              <div className="flex items-center justify-between mt-4">
                <span className="text-[12px] text-[#ee4d2d]">在 8 小时内过期</span>
                <button className="border border-[#ee4d2d] text-[#ee4d2d] bg-white px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4]">充值</button>
              </div>
            </div>
          </div>
        </div>

        {/* 3. 广告表现 (All Ads Performance) */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-6">
          {/* Tabs */}
          <div className="flex px-6 border-b border-[#ebebeb] text-[14px] pt-4">
            {['全部点击出价广告', '商品广告', '新商品广告', '店铺广告', '直播广告'].map((tab) => (
              <div
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`mr-8 pb-3 cursor-pointer relative transition-colors ${activeTab === tab ? 'text-[#ee4d2d] font-medium' : 'text-[#333] hover:text-[#ee4d2d]'}`}
              >
                {tab}
                {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-[#ee4d2d]"></div>}
              </div>
            ))}
          </div>

          <div className="p-6">
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-[18px] font-medium text-[#333]">所有广告表现</h2>
              <div className="flex items-center gap-3">
                <div className="border border-[#d9d9d9] px-3 py-1.5 rounded-sm text-[13px] text-[#333] flex items-center gap-2 cursor-pointer">
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                  昨天 (GMT+7)
                </div>
                <div className="border border-[#d9d9d9] px-3 py-1.5 rounded-sm text-[13px] text-[#333] flex items-center gap-2 cursor-pointer">
                  导出数据 <ChevronDownIcon />
                </div>
                <div className="border border-[#d9d9d9] px-3 py-1.5 rounded-sm text-[13px] text-[#999] flex items-center gap-2 cursor-pointer bg-[#fafafa]">
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                  更多指标 <ChevronDownIcon />
                </div>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              {performanceMetrics.map((item) => (
                <div key={item.label} className={`border border-[#ebebeb] rounded-[2px] p-4 shadow-sm border-t-[3px] ${item.color}`}>
                  <div className="text-[13px] text-[#666]">{item.label} <InfoIcon /></div>
                  <div className="text-[24px] font-medium text-[#333] mt-2">{item.value}</div>
                </div>
              ))}
            </div>

            {/* Empty Chart Placeholder */}
            <div className="h-[140px] border-b border-[#ebebeb] flex items-end justify-between px-2 pb-2 text-[12px] text-[#999] relative">
              {/* 图例 */}
              <div className="absolute top-0 right-4 flex items-center gap-4">
                <span className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-[#ffb537]"></div> 点击数</span>
                <span className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-[#f37021]"></div> 销售额</span>
                <span className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-[#9d54e0]"></div> 花费</span>
              </div>
              
              {/* X轴坐标 */}
              <span>00:00</span>
              <span>03:00</span>
              <span>06:00</span>
              <span>09:00</span>
              <span>12:00</span>
              <span>15:00</span>
              <span>18:00</span>
              <span>21:00</span>
              
              {/* 模拟的黄色轴线 */}
              <div className="absolute bottom-8 left-0 right-0 h-[2px] bg-[#ffb537]"></div>
            </div>
          </div>
        </section>

        {/* 4. 广告列表 (All Ads List) */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-10">
          <div className="p-6">
            <h2 className="text-[18px] font-medium text-[#333] mb-5">广告列表</h2>
            
            {/* Filter Row 1 */}
            <div className="flex items-center justify-between mb-4 text-[13px]">
              <div className="flex items-center gap-6">
                <span className="text-[#666]">广告状态</span>
                <div className="flex gap-2">
                  {['全部', '计划中', '进行中', '暂停中', '已结束', '已删除'].map(status => (
                    <button 
                      key={status} 
                      onClick={() => setListTab(status)}
                      className={`px-4 py-1.5 rounded-full border transition-colors ${listTab === status ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#555] hover:bg-[#fafafa]'}`}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-[#555] cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded-sm border-[#d9d9d9] text-[#ee4d2d] focus:ring-[#ee4d2d]" />
                  仅显示受 ROAS 保护的广告
                </label>
                <span className="text-[#999] cursor-pointer hover:text-[#333]">展开所有筛选 <ChevronDownIcon /></span>
              </div>
            </div>

            {/* Filter Row 2 */}
            <div className="flex items-center gap-3 mb-5">
              <div className="flex items-center border border-[#d9d9d9] rounded-sm h-9 px-3 w-[300px] focus-within:border-[#ee4d2d]">
                <input type="text" placeholder="搜索广告名称，商品名称，商品 ID" className="flex-1 outline-none text-[13px]" />
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="#999" strokeWidth="2" fill="none"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              </div>
              <div className="flex-1 max-w-[240px] border border-[#d9d9d9] rounded-sm h-9 px-3 flex items-center justify-between text-[13px] text-[#555] cursor-pointer">
                <span>全部类型 ×</span> <ChevronDownIcon />
              </div>
              <div className="flex-1 max-w-[240px] border border-[#d9d9d9] rounded-sm h-9 px-3 flex items-center justify-between text-[13px] text-[#555] cursor-pointer">
                <span>全部诊断状态</span> <ChevronDownIcon />
              </div>
              <div className="ml-auto border border-[#d9d9d9] rounded-sm h-9 px-4 flex items-center gap-2 text-[13px] text-[#333] cursor-pointer hover:bg-[#fafafa]">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                选择指标
              </div>
            </div>

            {/* Table */}
            <div className="border border-[#ebebeb] rounded-[2px] overflow-x-auto custom-scrollbar">
              <div className="min-w-[1300px]">
                {/* Table Header */}
                <div className={`grid ${tableGridCols} bg-[#fafafa] border-b border-[#ebebeb] px-4 py-3 text-[13px] text-[#666] font-medium items-center`}>
                  <div className="flex items-center"><input type="checkbox" className="w-4 h-4 rounded-sm border-[#ccc]" /></div>
                  <div>广告信息</div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">日预算 <SortIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">目标 ROAS <SortIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">诊断 <InfoIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">花费 <InfoIcon /> <SortIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">销售额 <SortIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">ROAS <InfoIcon /> <SortIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">曝光量 <InfoIcon /> <SortIcon /></div>
                  <div className="flex items-center cursor-pointer hover:text-[#333]">点击数 <SortIcon /></div>
                </div>

                {/* Table Body */}
                <div className="text-[13px] text-[#333]">
                  {adsList.map((row) => {
                    const isPaused = row.status === 'Paused';
                    const isEnded = row.status === 'Ended';
                    
                    return (
                      <div key={row.id} className={`grid ${tableGridCols} px-4 py-4 border-b border-[#ebebeb] last:border-b-0 items-start hover:bg-[#fafafa] transition-colors`}>
                        <div className="pt-2"><input type="checkbox" className="w-4 h-4 rounded-sm border-[#ccc]" /></div>
                        
                        {/* 广告信息列 */}
                        <div className="flex gap-3 pr-4 min-w-0">
                          <img src={row.image} alt="Ad" className="w-12 h-12 border border-[#ebebeb] rounded-sm object-cover bg-white" />
                          <div className="min-w-0 flex-1">
                            <div className="font-medium text-[#333] truncate flex items-center gap-1.5" title={row.name}>
                              {row.name}
                              {row.hasWarning && <WarningIcon />}
                            </div>
                            <div className="text-[12px] text-[#888] truncate mt-0.5">{row.type}</div>
                            <div className="text-[12px] text-[#888] truncate">{row.period}</div>
                            
                            <div className="flex items-center gap-2 mt-1.5">
                              <span className="flex items-center gap-1 text-[12px]">
                                <div className={`w-2 h-2 rounded-full ${isPaused ? 'bg-[#ffb537]' : isEnded ? 'bg-[#b2b2b2]' : 'bg-[#26b562]'}`}></div>
                                {row.statusLabel}
                              </span>
                              {row.roasProtected && (
                                <span className="border border-[#d9d9d9] text-[#999] px-1.5 py-[1px] rounded-sm text-[11px] flex items-center gap-1 bg-white">
                                  <ShieldIcon /> ROAS 保护
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* 数据列 */}
                        <div className="pt-2">{row.budget}</div>
                        <div className="pt-2">{row.targetRoas}</div>
                        <div className="pt-2">{row.diagnosis}</div>
                        <div className="pt-2">{row.expense}</div>
                        <div className="pt-2">{row.sales}</div>
                        <div className="pt-2">{row.roas}</div>
                        <div className="pt-2">{row.impressions}</div>
                        <div className="pt-2">{row.clicks}</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
            
            {/* 底部横向滚动条区域装饰 (还原截图里的加粗灰线) */}
            <div className="w-[60%] h-2 bg-[#d9d9d9] rounded-full mx-auto mt-4 mb-4"></div>

            {/* Pagination Placeholder */}
            <div className="flex items-center justify-end text-[13px] text-[#666] gap-2 mt-4">
              <button className="p-1 hover:text-[#333]">&lt;</button>
              <span className="px-2">1 / 8</span>
              <button className="p-1 hover:text-[#333]">&gt;</button>
              <div className="border border-[#d9d9d9] rounded-sm px-2 py-1 ml-2 flex items-center justify-between w-24 cursor-pointer bg-white">
                <span>20 / 页</span>
                <ChevronDownIcon />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
import React, { useState } from 'react';

interface ShopVoucherViewProps {
  readOnly?: boolean;
}

// ---------------- 常用图标组件 ----------------
const InfoIcon = () => (
  <svg viewBox="0 0 1024 1024" className="inline-block w-3.5 h-3.5 ml-1 text-[#b2b2b2] fill-current">
    <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path>
    <path d="M464 688h96v-96h-96v96zm48-392c-65.3 0-118.3 49.3-126.9 113.1l74 15.6c4.5-33.6 34.3-56.7 60.9-56.7 34.1 0 64 25.1 64 60 0 25.5-16.7 44.5-44.1 61.2l-23.9 14.6V560h80v-34.5l22.4-13.6c39-23.7 61.6-58.1 61.6-99.9 0-64-57.3-116-128-116z"></path>
  </svg>
);

// 装饰图标
const IconShop = () => (
  <svg width="20" height="20" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path 
      fillRule="evenodd" 
      clipRule="evenodd" 
      d="M14.875 5.625a2.183 2.183 0 01-2.188 2.188A2.183 2.183 0 0110.5 5.624a2.183 2.183 0 01-2.187 2.188 2.183 2.183 0 01-2.187-2.188 2.183 2.183 0 01-2.188 2.187 2.179 2.179 0 01-1.83-.99 2.174 2.174 0 01-.357-1.185v-.012l.62-2.481A2.5 2.5 0 014.796 1.25h11.408a2.5 2.5 0 012.426 1.894l.62 2.48V5.638a2.177 2.177 0 01-.357 1.186 2.18 2.18 0 01-1.83.99 2.183 2.183 0 01-2.188-2.187zM3 8.933V17.5c0 .69.56 1.25 1.25 1.25h12.5c.69 0 1.25-.56 1.25-1.25V8.933a3.44 3.44 0 01-3.125-.656 3.423 3.423 0 01-2.188.786 3.423 3.423 0 01-2.187-.786 3.424 3.424 0 01-2.188.786 3.423 3.423 0 01-2.187-.786A3.44 3.44 0 013 8.933zm8.208 6.066a.579.579 0 00-.22-.483 2.675 2.675 0 00-.768-.357 7.273 7.273 0 01-.899-.358c-.758-.371-1.137-.882-1.137-1.533a1.38 1.38 0 01.28-.856c.21-.263.488-.463.804-.579a3.121 3.121 0 011.166-.208c.388-.006.772.07 1.128.225.316.134.587.357.779.642.186.281.283.612.277.95h-1.405a.709.709 0 00-.222-.557.844.844 0 00-.589-.195.967.967 0 00-.607.168.508.508 0 00-.217.422.524.524 0 00.241.41c.262.167.548.294.847.377.346.104.68.244.996.417.632.364.949.866.949 1.506a1.43 1.43 0 01-.579 1.205c-.385.292-.914.438-1.586.438a3.186 3.186 0 01-1.289-.252 1.973 1.973 0 01-.868-.7A1.834 1.834 0 018 14.658h1.414a.91.91 0 00.241.695c.162.146.426.22.791.22a.91.91 0 00.55-.152.5.5 0 00.212-.422z" 
      fill="#EE4D2D"
    />
  </svg>
);
const IconProduct = () => (
  <svg width="20" height="20" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path fillRule="evenodd" clipRule="evenodd" d="M13.625 4.375V5h-6.25v-.625a3.125 3.125 0 116.25 0zM3.621 5h2.504v-.625a4.375 4.375 0 118.75 0V5h2.503a1.25 1.25 0 011.245 1.138l1.128 12.5A1.25 1.25 0 0118.506 20H2.492a1.25 1.25 0 01-1.245-1.362l1.129-12.5A1.25 1.25 0 013.62 5zm7.911 8.75a.705.705 0 01.063.327.607.607 0 01-.26.514 1.11 1.11 0 01-.669.185c-.444 0-.766-.09-.963-.268a1.11 1.11 0 01-.294-.847H7.688c-.009.441.114.875.351 1.246.263.38.63.676 1.058.853.496.21 1.03.314 1.57.307.818 0 1.462-.178 1.932-.533a1.74 1.74 0 00.704-1.468c0-.779-.385-1.39-1.156-1.834a6.322 6.322 0 00-1.212-.508 3.812 3.812 0 01-1.032-.459.638.638 0 01-.294-.5.619.619 0 01.264-.513c.217-.15.477-.222.74-.205.26-.015.517.07.717.238a.864.864 0 01.27.677h1.712a2.034 2.034 0 00-.338-1.156 2.165 2.165 0 00-.949-.782 3.295 3.295 0 00-1.373-.273 3.801 3.801 0 00-1.42.253c-.385.14-.723.384-.978.704a1.68 1.68 0 00-.342 1.043c0 .793.461 1.415 1.384 1.867.355.17.72.316 1.095.437.333.094.649.24.935.434.089.07.16.16.206.262z" fill="#EE4D2D"></path>
  </svg>
);
const IconPrivate = () => (
  <svg width="20" height="20" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path fillRule="evenodd" clipRule="evenodd" d="M19.875 3.75c.345 0 .625.28.625.625v11.25c0 .345-.28.625-.625.625H1.125a.625.625 0 01-.625-.625V15a1.25 1.25 0 000-2.5v-1.25a1.25 1.25 0 000-2.5V7.5A1.25 1.25 0 00.5 5v-.625c0-.345.28-.625.625-.625h18.75zm-5.103 7.744a.782.782 0 01.07.363.677.677 0 01-.288.57c-.22.147-.48.219-.744.206-.494 0-.851-.1-1.07-.298a1.231 1.231 0 01-.327-.94h-1.912c-.01.49.126.971.39 1.384.292.422.7.75 1.175.947.551.233 1.145.35 1.744.341.91 0 1.625-.197 2.147-.592a1.932 1.932 0 00.782-1.63c0-.866-.428-1.546-1.284-2.039a7.02 7.02 0 00-1.347-.565 4.236 4.236 0 01-1.147-.51.71.71 0 01-.326-.554.688.688 0 01.294-.57c.24-.166.53-.247.821-.229.29-.016.575.079.797.265a.959.959 0 01.3.752h1.903a2.26 2.26 0 00-.376-1.284 2.406 2.406 0 00-1.054-.869 3.66 3.66 0 00-1.527-.304 4.224 4.224 0 00-1.577.282 2.486 2.486 0 00-1.087.782c-.253.333-.386.741-.38 1.159 0 .88.513 1.572 1.539 2.075.394.188.8.35 1.216.484.37.105.72.268 1.04.483a.782.782 0 01.228.29zM5.5 5h1.25v2.5H5.5V5zm0 3.75h1.25v2.5H5.5v-2.5zm1.25 3.75H5.5V15h1.25v-2.5z" fill="#EE4D2D"></path>
  </svg>
);
const IconLive = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="#ee4d2d"><path d="M17 10.5V7c0-.6-.4-1-1-1H4c-.6 0-1 .4-1 1v10c0 .6.4 1 1 1h12c.6 0 1-.4 1-1v-3.5l4 4v-11l-4 4z"></path></svg>;
const IconVideo = () => (
  <svg width="20" height="20" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path fillRule="evenodd" clipRule="evenodd" d="M6.34.584C5.207-.008 3.807.149 2.725.707 1.64 1.266.708 2.319.708 3.687v12.626c0 1.368.932 2.42 2.017 2.98 1.082.558 2.482.714 3.615.123l12.105-6.313c2.462-1.284 2.462-4.922 0-6.206L6.34.584zm1.47 13.449a3.624 3.624 0 01-.841-.305 5.487 5.487 0 01-.632-.381c-.165-.14-.306-.261-.42-.363l.63-.896-.63.896c.114.102.255.223.42.363.179.127.39.254.632.38.242.128.522.23.841.306zm-.88-.231a3.7 3.7 0 00.86.312c.326.09.697.136 1.11.136.843 0 1.544-.207 2.097-.627.56-.425.836-1.043.836-1.84 0-.432-.098-.799-.3-1.095a2.548 2.548 0 00-.751-.748c-.3-.195-.631-.35-.994-.467a13.67 13.67 0 00-1.037-.326A4.292 4.292 0 018.342 9a2.278 2.278 0 01-.403-.256 1.208 1.208 0 01-.287-.321.75.75 0 01-.103-.394.813.813 0 01.401-.694l.003-.002c.266-.18.562-.271.89-.271.789 0 1.46.193 2.018.576l.069.047.706-1.012-.067-.048a4.914 4.914 0 00-1.206-.64c-.42-.157-.92-.234-1.501-.234a2.979 2.979 0 00-1.792.609 2.361 2.361 0 00-.614.73l-.001.002c-.147.28-.22.6-.22.954 0 .275.04.526.12.753l.001.004c.092.223.21.426.356.61l.002.003a2.727 2.727 0 001.065.767c.284.116.587.219.908.308.329.088.632.19.909.302.272.111.491.252.66.42l.005.005c.172.148.258.34.258.583a1.002 1.002 0 01-.442.83c-.277.192-.649.303-1.123.328a3.377 3.377 0 01-1.23-.204 3.405 3.405 0 01-1.118-.726l-.07-.067-.73 1.036.055.05c.116.102.256.223.423.363l.005.004c.182.13.396.26.64.388z" fill="#EE4D2D"></path>
  </svg>
);
const IconFollow = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="#ee4d2d"><path d="M15 12c2.2 0 4-1.8 4-4s-1.8-4-4-4-4 1.8-4 4 1.8 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.7 0-8 1.3-8 4v2h16v-2c0-2.7-5.3-4-8-4z"></path></svg>;

export default function ShopVoucherView({ readOnly = false }: ShopVoucherViewProps) {
  const[activeTab, setActiveTab] = useState('全部');
  const[isVoucherTypesExpanded, setIsVoucherTypesExpanded] = useState(false);

  // ---------------- 模拟数据 ----------------
  const metrics =[
    { label: '销售额', value: 'RM 0', change: '0.00%' },
    { label: '订单数', value: '0', change: '0.00%' },
    { label: '使用率', value: '0.00 %', change: '0.00%' },
    { label: '买家数', value: '0', change: '0.00%' },
  ];

  const mockVouchers =[
    {
      id: 'HOME9018',
      type: 'Product Voucher', // 后续渲染翻译为: 商品代金券
      typeLabel: '商品代金券',
      discountType: 'percent', // 决定图标是 % 还是金额符号
      discountValue: '90%',
      discountLabel: '90%OFF',
      status: 'Expired',
      statusLabel: '已结束',
      scope: '1 个商品',
      limit: 20000,
      used: 2,
      period: '18/03/2026 14:24 - 31/03/2026 15:24',
      actions:['详情', '订单']
    },
    {
      id: 'HOME9003H',
      type: 'Product Voucher',
      typeLabel: '商品代金券',
      discountType: 'percent',
      discountValue: '90%',
      discountLabel: '90%OFF',
      status: 'Expired',
      statusLabel: '已结束',
      scope: '4 个商品',
      limit: 20000,
      used: 3,
      period: '13/03/2026 16:37 - 16/03/2026 19:19',
      actions: ['详情', '订单']
    },
    {
      id: 'SFP-1372839232696320',
      type: 'Follow Prize Voucher',
      typeLabel: '关注礼',
      discountType: 'percent',
      discountValue: '5%',
      discountLabel: '5%OFF',
      status: 'Ongoing',
      statusLabel: '进行中',
      scope: '所有商品',
      limit: 10000,
      used: 1,
      period: '10/03/2026 10:55 - 13/09/2026 10:55',
      actions:['编辑', '订单', '结束']
    },
    {
      id: 'HOME4515H',
      type: 'Shop Voucher',
      typeLabel: '店铺代金券',
      discountType: 'fixed',
      discountValue: '1500-45', // 满1500减45
      discountLabel: 'RM 45',
      status: 'Ongoing',
      statusLabel: '进行中',
      scope: '所有商品',
      limit: 100000,
      used: 0,
      period: '02/03/2026 08:40 - 02/06/2026 09:40',
      actions:['编辑', '分享', '更多']
    }
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto max-w-[1660px]">
        
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览代金券页，但无法创建或编辑活动。
          </div>
        )}

        {/* 1. 创建代金券 (Create Voucher) 导航卡片区 - 【已增加白底外框和内边距，完美还原截图2】 */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-6 p-6">
          <div className="mb-6">
            <h2 className="text-[20px] font-medium text-[#333]">创建代金券</h2>
            <p className="text-[13px] text-[#999] mt-1">在您的店铺中为商品创建代金券！</p>
          </div>

          {/* 类目: 提升日常转化 */}
          <div className="mb-6">
            <h3 className="text-[16px] font-medium text-[#333] mb-4">提升日常转化</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white border border-[#ebebeb] p-5 rounded-[2px] flex flex-col justify-between h-[140px]">
                <div>
                  <div className="flex items-center gap-2 text-[15px] font-medium text-[#333] mb-1.5"><IconShop /> 店铺代金券</div>
                  <div className="text-[13px] text-[#888] leading-tight pr-10">适用于您店铺内所有商品的代金券，提升全店销量</div>
                </div>
                <div className="flex justify-end mt-2">
                  <button disabled={readOnly} className="border border-[#ee4d2d] text-[#ee4d2d] px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">创建</button>
                </div>
              </div>
              <div className="bg-white border border-[#ebebeb] p-5 rounded-[2px] flex flex-col justify-between h-[140px]">
                <div>
                  <div className="flex items-center gap-2 text-[15px] font-medium text-[#333] mb-1.5"><IconProduct /> 商品代金券</div>
                  <div className="text-[13px] text-[#888] leading-tight pr-10">适用于选定商品的代金券，开展专属商品促销</div>
                </div>
                <div className="flex justify-end mt-2">
                  <button disabled={readOnly} className="border border-[#ee4d2d] text-[#ee4d2d] px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">创建</button>
                </div>
              </div>
            </div>
          </div>

          {/* 类目: 指定发放渠道 */}
          <div className="mb-6">
            <h3 className="text-[16px] font-medium text-[#333] mb-4">指定发放渠道</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white border border-[#ebebeb] p-5 rounded-[2px] flex flex-col justify-between h-[140px]">
                <div>
                  <div className="flex items-center gap-2 text-[15px] font-medium text-[#333] mb-1.5"><IconPrivate /> 专属代金券</div>
                  <div className="text-[13px] text-[#888] leading-tight pr-4">仅通过分享兑换码发放给指定买家的代金券</div>
                </div>
                <div className="flex justify-end mt-2">
                  <button disabled={readOnly} className="border border-[#ee4d2d] text-[#ee4d2d] px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">创建</button>
                </div>
              </div>
              <div className="bg-white border border-[#ebebeb] p-5 rounded-[2px] flex flex-col justify-between h-[140px]">
                <div>
                  <div className="flex items-center gap-2 text-[15px] font-medium text-[#333] mb-1.5"><IconLive /> 直播代金券</div>
                  <div className="text-[13px] text-[#888] leading-tight pr-4">仅在直播间展示并可用的代金券，提升直播转化</div>
                </div>
                <div className="flex justify-end mt-2">
                  <button disabled={readOnly} className="border border-[#ee4d2d] text-[#ee4d2d] px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">创建</button>
                </div>
              </div>
              <div className="bg-white border border-[#ebebeb] p-5 rounded-[2px] flex flex-col justify-between h-[140px]">
                <div>
                  <div className="flex items-center gap-2 text-[15px] font-medium text-[#333] mb-1.5"><IconVideo /> 视频代金券</div>
                  <div className="text-[13px] text-[#888] leading-tight pr-4">适用于您视频中展示的商品，增加视频带货销量</div>
                </div>
                <div className="flex justify-end mt-2">
                  <button disabled={readOnly} className="border border-[#ee4d2d] text-[#ee4d2d] px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">创建</button>
                </div>
              </div>
            </div>
          </div>

           {/* 类目: 指定买家群体 */}
           <div 
            className={`grid transition-all duration-300 ease-in-out ${
              isVoucherTypesExpanded ? 'grid-rows-[1fr] opacity-100 mt-6' : 'grid-rows-[0fr] opacity-0 mt-0'
            }`}
          >
            <div className="overflow-hidden">
              <h3 className="text-[16px] font-medium text-[#333] mb-4">指定买家群体</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white border border-[#ebebeb] p-5 rounded-[2px] flex flex-col justify-between h-[140px]">
                  <div>
                    <div className="flex items-center gap-2 text-[15px] font-medium text-[#333] mb-1.5"><IconFollow /> 关注礼代金券</div>
                    <div className="text-[13px] text-[#888] leading-tight pr-4">奖励代金券给新关注者，鼓励买家关注您的店铺。</div>
                  </div>
                  <div className="flex justify-end mt-2">
                    <button disabled={readOnly} className="border border-[#ee4d2d] text-[#ee4d2d] px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4] disabled:opacity-50 disabled:cursor-not-allowed">创建</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 底部展开/收起按钮 (通过绝对定位背景色完美遮挡虚线) */}
          <div className="mt-8 mb-2 relative flex items-center justify-center">
             <div className="absolute left-0 right-0 h-px border-t border-dashed border-[#e5e5e5]"></div>
             <div 
               onClick={() => setIsVoucherTypesExpanded(!isVoucherTypesExpanded)}
               className="bg-white px-4 relative text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center select-none"
             >
               {isVoucherTypesExpanded ? '收起代金券类型' : '更多指定买家的代金券类型'}
               <svg 
                 className={`w-3.5 h-3.5 ml-1 text-[#05a] transform transition-transform duration-300 ${isVoucherTypesExpanded ? '' : 'rotate-180'}`} 
                 viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               >
                 <polyline points="18 15 12 9 6 15"></polyline>
               </svg>
             </div>
          </div>
        </section>


        {/* 2. 代金券表现 (Voucher Performance) 面板 */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-6">
          <div className="px-6 py-4 flex justify-between items-center border-b border-[#ebebeb]">
            <div className="flex items-center gap-3">
              <h2 className="text-[18px] font-medium text-[#333]">代金券表现</h2>
              <span className="text-[13px] text-[#999]">(数据截至于 23-04-2026 至 30-04-2026 GMT+7)</span>
            </div>
            <button className="text-[14px] text-[#05a] hover:underline">更多 &gt;</button>
          </div>

          <div className="grid grid-cols-4 py-6">
            {metrics.map((item, index) => (
              <div key={item.label} className={`px-6 ${index !== 3 ? 'border-r border-[#ebebeb]' : ''}`}>
                <div className="text-[13px] text-[#666]">{item.label} <InfoIcon /></div>
                <div className="mt-2 text-[24px] text-[#333]">{item.value}</div>
                <div className="mt-1 text-[12px] text-[#999]">较前7天 <span className="text-[#333]">{item.change}</span></div>
              </div>
            ))}
          </div>
        </section>


        {/* 3. 代金券列表 (Vouchers List) 面板 */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] pb-10">
          <div className="px-6 pt-6 pb-4">
             <h2 className="text-[18px] font-medium text-[#333]">代金券列表</h2>
          </div>

          {/* Tabs */}
          <div className="flex px-6 border-b border-[#ebebeb] text-[14px]">
            {['全部', '进行中', '即将开始', '已结束'].map((tab) => (
              <div
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`mr-8 pb-3 cursor-pointer relative transition-colors ${activeTab === tab ? 'text-[#ee4d2d] font-medium' : 'text-[#333] hover:text-[#ee4d2d]'}`}
              >
                {tab}
                {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#ee4d2d]"></div>}
              </div>
            ))}
          </div>

          {/* Search/Filter Bar */}
          <div className="px-6 py-5 flex items-center gap-3 text-[14px]">
            <span className="text-[#333]">搜索</span>
            <div className="flex border border-[#d9d9d9] rounded-sm overflow-hidden h-[34px] w-[400px]">
               <div className="px-3 bg-[#fafafa] border-r border-[#d9d9d9] flex items-center text-[#666] cursor-pointer">代金券名称 <svg className="w-3 h-3 ml-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg></div>
               <input type="text" className="flex-1 px-3 outline-none text-[13px]" />
            </div>
            <button className="border border-[#ee4d2d] text-[#ee4d2d] px-5 h-[34px] rounded-sm hover:bg-[#fff6f4] transition-colors">查询</button>
          </div>

          {/* Table */}
          <div className="px-6">
            <div className="w-full border border-[#ebebeb] rounded-[2px] overflow-hidden">
              
              {/* Header */}
              <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr_0.8fr_1.8fr_0.8fr] bg-[#fafafa] border-b border-[#ebebeb] px-4 py-3 text-[13px] text-[#666] font-medium items-center">
                <div>代金券名称 | 代码</div>
                <div>代金券类型</div>
                <div className="flex items-center">适用商品 <InfoIcon /></div>
                <div>优惠内容</div>
                <div className="flex items-center">发放总量 <InfoIcon /></div>
                <div className="flex items-center">已使用 <InfoIcon /></div>
                <div>领取期间</div>
                <div>操作</div>
              </div>

              {/* Body */}
              <div className="text-[13px] text-[#333]">
                {mockVouchers.map((row, i) => {
                  const isPercent = row.discountType === 'percent';
                  const isOngoing = row.status === 'Ongoing';

                  return (
                    <div key={i} className="grid grid-cols-[1.6fr_1fr_1fr_1fr_1fr_0.8fr_1.8fr_0.8fr] border-b border-[#ebebeb] last:border-b-0 px-4 py-4 items-start hover:bg-[#fafafa] transition-colors">
                      
                      {/* 列1: 名称、图标与标签 */}
                      <div className="flex gap-3 pr-2 min-w-0">
                        {/* 仿 Shopee 的彩色正方形 Logo */}
                        <div className={`w-[52px] h-[52px] flex items-center justify-center text-white text-[24px] font-bold rounded-sm flex-shrink-0 ${isPercent ? 'bg-[#ff7337]' : 'bg-[#55b5d9]'}`}>
                          {isPercent ? '%' : '$'}
                        </div>
                        <div className="min-w-0">
                          {/* 状态 Tag */}
                          <div className={`inline-block px-1.5 py-0.5 text-[12px] rounded-sm mb-1 leading-none ${isOngoing ? 'bg-[#e5f5f0] text-[#00bfa5]' : 'bg-[#f5f5f5] text-[#999]'}`}>
                            {row.statusLabel}
                          </div>
                          <div className="font-medium text-[#333] truncate" title={row.discountValue}>{row.discountValue}</div>
                          <div className="text-[#999] text-[12px] truncate mt-0.5">代码:{row.id}</div>
                        </div>
                      </div>

                      {/* 其他列数据 */}
                      <div className="text-[#666] truncate min-w-0 pr-2" title={row.typeLabel}>{row.typeLabel}</div>
                      <div className="text-[#666]">{row.scope}</div>
                      <div className="text-[#666]">{row.discountLabel}</div>
                      <div className="text-[#666] flex items-center gap-1">{row.limit} <svg className="w-3 h-3 text-[#b2b2b2] cursor-pointer" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg></div>
                      <div className="text-[#666]">{row.used}</div>
                      <div className="text-[#666] pr-4">{row.period}</div>
                      
                      {/* 操作列 */}
                      <div className="flex flex-col gap-1.5 items-start">
                        {row.actions.map(act => (
                          <button key={act} className="text-[#05a] hover:underline leading-none">{act}</button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

            </div>

            {/* 分页器 Placeholder */}
            <div className="flex items-center justify-end mt-5 text-[13px] text-[#666] gap-2">
              <button className="p-1 text-[#ccc] cursor-not-allowed">&lt;</button>
              <button className="px-2 text-[#ee4d2d]">1</button>
              <button className="px-2 hover:text-[#ee4d2d]">2</button>
              <button className="px-2 hover:text-[#ee4d2d]">3</button>
              <button className="px-2 hover:text-[#ee4d2d]">4</button>
              <button className="px-2 hover:text-[#ee4d2d]">5</button>
              <span>...</span>
              <button className="px-2 hover:text-[#ee4d2d]">20</button>
              <button className="p-1 hover:text-[#ee4d2d]">&gt;</button>
              <div className="flex items-center ml-2">
                <span className="mr-2">跳转至</span>
                <input type="text" defaultValue="1" className="border border-[#e5e5e5] w-10 h-7 text-center rounded-sm outline-none focus:border-[#ccc]" />
                <span className="ml-2">页</span>
                <button className="ml-3 border border-[#e5e5e5] px-3 h-7 rounded-sm hover:bg-[#fafafa]">Go</button>
              </div>
            </div>

          </div>
        </section>
      </div>
    </div>
  );
}
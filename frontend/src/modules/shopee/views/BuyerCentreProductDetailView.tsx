import React from 'react';
import { 
  ShoppingCart, 
  MessageCircle, 
  Store, 
  ChevronRight, 
  ChevronDown, // 补上这个
  CheckCircle2, 
  ShieldCheck, 
  Globe,       // 补上这个 (跨境栏用到了)
  Plus, 
  Minus,
  Star
} from 'lucide-react';

interface BuyerCentreProductDetailViewProps {
  listingId: number | null;
  onBackToBuyerCentre: () => void;
  onBackToSellerCentre: () => void;
}

// --- 模拟 SKU 数据 ---
const mockSkus = [
  { id: 1, name: "白色-1个袋装", price: "0.8", stock: "975452", img: "白" },
  { id: 2, name: "黑色-1个袋装", price: "0.8", stock: "989018", img: "黑" },
  { id: 3, name: "白色-2个袋装", price: "1.6", stock: "999752", img: "白2" },
  { id: 4, name: "黑色-2个袋装", price: "1.6", stock: "999500", img: "黑2" },
  { id: 5, name: "混色-2个袋装", price: "1.6", stock: "999969", img: "混" },
  { id: 6, name: "售后详情", price: "0.4", stock: "99999", img: "售" },
];

export default function BuyerCentreProductDetailView({
  listingId,
  onBackToBuyerCentre,
  onBackToSellerCentre,
}: BuyerCentreProductDetailViewProps) {
  return (
    <div className="fixed inset-0 bg-[#f5f5f5] overflow-y-auto">
      {/* 头部导航 (保持你的原代码不变) */}
      <header className="bg-[#ee4d2d] w-full">
        <div className="max-w-[1200px] mx-auto px-4">
          <nav className="flex items-center justify-between py-1.5 text-[13px] text-white">
            <div className="flex items-center gap-2.5 font-light"></div>
            <div className="flex items-center gap-4 font-light">
              <button type="button" onClick={onBackToBuyerCentre} className="hover:text-white/80 transition">返回买家中心</button>
              <button type="button" onClick={onBackToSellerCentre} className="hover:text-white/80 transition">返回卖家中心</button>
            </div>
          </nav>

          <div className="flex items-start py-4 gap-10">
            <button type="button" onClick={onBackToBuyerCentre} className="flex items-center gap-2.5 mt-0.5 shrink-0 text-white hover:opacity-90 transition-opacity text-left">
              <svg viewBox="0 0 40 44" className="h-[46px] w-auto fill-current" xmlns="http://www.w3.org/2000/svg">
                <path d="M25.914134 32.7635637c-.249117 2.0382156-1.4950636 3.6705591-3.4249956 4.4880861-1.0746788.4552057-2.5177827.7009698-3.659991.6239878-1.7820188-.0675851-3.4559541-.4971301-4.9989944-1.282491-.5512798-.2804602-1.3730398-.8410192-2.0039791-1.3659785-.1598621-.1326403-.1788717-.2175735-.0731419-.3662969.05721-.0854754.1623968-.2392586.3952197-.577365.3374665-.4900825.3796498-.5517042.4176691-.6091696.1079024-.1642644.2833343-.1785404.4564126-.0435509.0182855.0140953.0182855.0140953.0320449.0247571.0282429.0216851.0282429.0216851.0952293.0733678.0678916.0522249.1080834.0831261.1243774.0954143 1.6639779 1.2918879 3.6022379 2.0371314 5.5589643 2.1115835 2.7221817-.0366839 4.6798134-1.2501442 5.0304962-3.1132529.3858053-2.0506845-1.2379807-3.8218124-4.4149456-4.8090251-.993571-.3088315-3.5050171-1.3052603-3.9679473-1.5745165-2.1747038-1.2646009-3.1914485-2.92134-3.0467941-4.9675068.2214172-2.8364068 2.8776987-4.9519659 6.2338974-4.9658804 1.5010381-.0030721 2.9988173.3059401 4.4377572.9071586.5094586.2128751 1.4192061.7034997 1.7331368.9358914.1808633.1317368.216529.2851586.1129717.4508687-.0579342.0957757-.1537066.2481133-.3552089.5652574l-.0023536.0036142c-.265773.4179796-.27392.4309907-.3349319.5287542-.1051867.1588431-.2288399.1738419-.4189364.0543934-1.5396005-1.0253423-3.2464859-1.5412662-5.123734-1.5784922-2.3371005.0459-4.0887038 1.4245282-4.204029 3.3028164-.0304154 1.6964951 1.2530074 2.9348932 4.0255194 3.8790971 5.6279422 1.792813 7.7816449 3.8946381 7.3762868 7.2084778M18.9638444 3.47806106c3.6639739 0 6.6506613 3.44702216 6.7904275 7.76162774h-13.580674c.1395851-4.31460558 3.1262725-7.76162774 6.7902465-7.76162774m18.962577 8.57282994c0-.4479773-.36408-.8112022-.8128888-.8112022h-8.8025535C28.0948122 5.54266018 23.9927111 1 18.9638444 1c-5.0288668 0-9.1309679 4.54266018-9.34713476 10.2396888l-8.8150456.0001807c-.44192907.0079512-.79786211.3679233-.79786211.8110215 0 .0211429.00090522.0421052.00235358.0628867H0l1.25662829 27.4585357c0 .0762592.00289671.1534219.00869013.230946.00126731.0175288.00271566.0348768.00416402.0522249l.00271566.0580075.00289671.0030721c.1910017 1.9106351 1.58974975 3.4493714 3.49198192 3.5203899l.00434506.0043371H32.7338906c.0132163.0001807.0264325.0001807.0398298.0001807.0132162 0 .0264324 0 .0396487-.0001807h.0595635l.0012674-.0010843c1.9351822-.0524056 3.5028445-1.6128269 3.6685-3.5471349l.0009053-.0009035.0012673-.0260221c.0016294-.0202394.0030777-.0406595.004345-.0608989.0030778-.0487914.0050693-.0972214.0057934-.1456514l1.3712294-27.566961h-.0009053c.0007242-.0137339.0010863-.0278292.0010863-.0417438"></path>
              </svg>
              <span className="text-[32px] font-semibold tracking-widest font-sans">虾皮购物</span>
            </button>

            <div className="flex-1 flex flex-col gap-1.5 ml-2">
              <div className="h-[44px] bg-white rounded-sm shadow-sm flex items-center px-4 text-sm text-gray-400">
                商品详情页占位，后续接入主商品详情数据
              </div>
              <div className="flex items-center gap-2 text-[12px] text-white">
                <button type="button" onClick={onBackToBuyerCentre} className="hover:text-white/80">买家中心</button>
                <span>/</span>
                <span>商品详情</span>
              </div>
            </div>

            <div className="mt-2 shrink-0 px-4 text-white">
              <ShoppingCart size={28} strokeWidth={1.5} />
            </div>
          </div>
        </div>
      </header>

      {/* 主体详情区 */}
      <main className="max-w-[1200px] mx-auto py-5 pb-20">
        <div className="bg-white shadow-sm border border-gray-100 rounded-lg overflow-hidden">
          {/* 使用 Grid 布局分为左右两栏 */}
          <div className="grid grid-cols-[420px_1fr] gap-8 p-6">
            
            {/* ==================== 左侧：店铺信息 + 轮播图 ==================== */}
            <div className="flex flex-col gap-4">
              
              {/* 店铺信息卡片 */}
              <div className="border border-gray-200 rounded-md p-4 bg-[#fafafa]">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-[15px] font-medium text-gray-800 line-clamp-1 leading-tight flex items-center gap-1">
                      潮州市潮安区金石镇壕壕福五金... <ChevronDown size={16} className="text-gray-400"/>
                    </h3>
                    <p className="text-[12px] text-gray-500 mt-1">入驻2年</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button className="flex items-center gap-1 border border-gray-300 rounded px-2 py-1 text-[12px] hover:bg-gray-50 transition">
                      <Plus size={12} /> 关注
                    </button>
                    <button className="flex items-center gap-1 border border-gray-300 rounded px-2 py-1 text-[12px] hover:bg-gray-50 transition">
                      <MessageCircle size={12} /> 客服
                    </button>
                    <button className="flex items-center gap-1 border border-gray-300 rounded px-2 py-1 text-[12px] hover:bg-gray-50 transition">
                      <Store size={12} /> 商品
                    </button>
                  </div>
                </div>
                {/* 店铺数据 */}
                <div className="flex items-center justify-between text-[12px] text-gray-500 mt-4 border-t border-gray-200 pt-3">
                  <span>店铺回头率 <span className="text-gray-800 font-semibold">55%</span></span>
                  <span>店铺服务分 <span className="text-gray-800 font-semibold">4.0分</span></span>
                  <span>准时发货率 <span className="text-gray-800 font-semibold">100%</span></span>
                  <span>店铺好评率 <span className="text-gray-800 font-semibold">90.0%</span></span>
                </div>
              </div>

              {/* 商品主图 */}
              <div className="aspect-square bg-gray-100 rounded-md overflow-hidden relative cursor-pointer group">
                {/* 模拟一张灰色主图，带有一点渐变效果 */}
                <div className="w-full h-full bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center text-gray-500">
                  商品实拍图区域
                </div>
              </div>

              {/* 商品缩略图列表 */}
              <div className="grid grid-cols-6 gap-2">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className={`aspect-square rounded border-2 cursor-pointer overflow-hidden ${index === 0 ? 'border-[#ff5000]' : 'border-transparent hover:border-gray-300'} bg-gray-100 flex items-center justify-center text-[10px] text-gray-400`}>
                    图{index + 1}
                  </div>
                ))}
                {/* 最后一个是更多参数图标 */}
                <div className="aspect-square rounded border border-gray-200 cursor-pointer flex flex-col items-center justify-center text-[12px] text-gray-600 bg-gray-50 hover:bg-gray-100">
                  参数
                </div>
              </div>
            </div>

            {/* ==================== 右侧：商品详细信息 ==================== */}
            <div className="flex flex-col">
              
              {/* 标题区 */}
              <h1 className="text-xl font-bold text-gray-900 leading-snug">
                <span className="bg-[#ff5000] text-white text-[12px] px-1.5 py-0.5 rounded-sm mr-2 align-middle font-normal">镇店之宝</span>
                跨境爆款钩子免打孔无痕厚挂钩门后收纳粘钩浴室卧室挂勾现货批发
              </h1>

              {/* 副标签 */}
              <div className="flex items-center gap-3 mt-3 text-[12px]">
                <span className="bg-[#fff1eb] text-[#ff5000] px-2 py-1 rounded-sm flex items-center gap-1">
                  AI严选指数4.6 <ChevronRight size={12} />
                </span>
                <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-sm">
                  商品复购率53.33%
                </span>
              </div>

              {/* 价格区块 */}
              <div className="bg-[#fff8f6] rounded-md mt-4 p-4 pb-3">
                <div className="flex items-end justify-between">
                  <div className="flex items-baseline gap-2 text-[#ff5000]">
                    <span className="text-[13px] text-[#ff5000]">券后</span>
                    <span className="text-lg font-bold">¥</span>
                    <span className="text-4xl font-bold tracking-tight leading-none">0.40</span>
                    <span className="text-sm font-medium">起</span>
                    
                    <span className="text-gray-400 text-sm ml-4 line-through">¥0.40 ~ ¥1.60</span>
                  </div>
                  <div className="text-gray-500 text-[13px]">已售3.9万+个</div>
                </div>
                <div className="text-[12px] text-gray-500 mt-1">首件预估到手价</div>
                
                {/* 优惠标签 */}
                <div className="flex items-center gap-4 mt-3 text-[12px] text-[#ff5000]">
                  <span className="flex items-center gap-1 cursor-pointer">限时5折·首单减1元 <ChevronDown size={14}/></span>
                  <span className="text-gray-300">|</span>
                  <span className="flex items-center gap-1 cursor-pointer">先采后付0元下单 <ChevronRight size={14}/></span>
                </div>
              </div>

              {/* 物流与服务 (仿 1688 表格样式) */}
              <div className="mt-5 space-y-3 text-[13px] border-b border-gray-100 pb-5">
                <div className="flex items-center text-gray-500">
                  <span className="w-[60px] shrink-0 flex items-center gap-1"><ShieldCheck size={14}/> 发货</span>
                  <div className="flex-1 text-gray-700 flex items-center gap-3">
                    广东潮州 <span className="text-gray-400">送至</span> 福建厦门 <ChevronDown size={14} className="text-gray-400 cursor-pointer"/>
                    <span>2件以内 现在付款，预计后天达 <ChevronDown size={14} className="text-gray-400 cursor-pointer"/></span>
                    <span>运费 <span className="text-[#ff5000]">¥3</span> 起</span>
                  </div>
                </div>
                <div className="flex items-center text-gray-500">
                  <span className="w-[60px] shrink-0 flex items-center gap-1"><CheckCircle2 size={14}/> 保障</span>
                  <div className="flex-1 text-gray-700 flex items-center gap-2 cursor-pointer">
                    退货包运费 · 7天无理由退货 · 晚发必赔 · 极速退款 <ChevronDown size={14} className="text-gray-400"/>
                  </div>
                </div>
                <div className="flex items-center text-gray-500">
                  <span className="w-[60px] shrink-0 flex items-center gap-1"><Globe size={14}/> 跨境</span>
                  <div className="flex-1 text-gray-700 flex items-center gap-2 cursor-pointer">
                    支持跨境贴标 · 支持贴箱唛 <ChevronDown size={14} className="text-gray-400"/>
                  </div>
                </div>
              </div>

              {/* SKU 选择区 */}
              <div className="mt-5">
                <div className="flex text-[13px] text-gray-500 mb-3">
                  <span className="w-14">颜色</span>
                </div>
                
                {/* SKU 列表 */}
                <div className="space-y-3 max-h-[220px] overflow-y-auto pr-2 custom-scrollbar">
                  {mockSkus.map((sku) => (
                    <div key={sku.id} className="flex items-center justify-between text-[13px]">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-gray-100 rounded border border-gray-200 flex items-center justify-center text-[10px] text-gray-400">
                          {sku.img}
                        </div>
                        <span className="text-gray-800">{sku.name}</span>
                      </div>
                      <div className="flex items-center gap-6">
                        <span className="font-semibold text-gray-900 w-10 text-right">¥{sku.price}</span>
                        <span className="text-gray-400 w-[100px] text-right">库存{sku.stock}个</span>
                        
                        {/* 数量加减器 */}
                        <div className="flex items-center border border-gray-300 rounded-sm">
                          <button className="w-7 h-7 bg-gray-50 flex items-center justify-center text-gray-400 hover:bg-gray-100 transition">
                            <Minus size={14} />
                          </button>
                          <input 
                            type="text" 
                            defaultValue="0" 
                            className="w-10 h-7 text-center text-[13px] border-x border-gray-300 outline-none"
                          />
                          <button className="w-7 h-7 bg-gray-50 flex items-center justify-center text-gray-600 hover:bg-gray-100 transition">
                            <Plus size={14} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 操作按钮区 */}
              <div className="mt-8 flex items-center gap-3">
                <button className="flex-1 h-12 bg-[#ff5000] hover:bg-[#e64800] text-white rounded text-[15px] font-medium transition-colors">
                  立即下单
                </button>
                <button className="flex-1 h-12 border border-[#ff5000] text-[#ff5000] bg-[#fff8f6] hover:bg-[#ffeae3] rounded text-[15px] font-medium transition-colors">
                  加采购车
                </button>
                <button className="flex-1 h-12 border border-[#ff5000] text-[#ff5000] rounded text-[15px] font-medium transition-colors">
                  跨境铺货
                </button>
                {/* 收藏按钮 */}
                <button className="flex flex-col items-center justify-center ml-2 text-gray-500 hover:text-[#ff5000] transition-colors w-16">
                  <Star size={20} />
                  <span className="text-[12px] mt-1">收藏 (67)</span>
                </button>
              </div>

              {/* 底部附加信息 */}
              <div className="mt-6 flex items-center justify-between text-[13px] bg-[#fafafa] p-3 rounded text-gray-600 border border-gray-100">
                <div className="flex items-center gap-4">
                  <span className="font-medium text-gray-800 flex items-center gap-1">密文代发 <span className="bg-[#ff5000] text-white text-[10px] px-1 rounded-sm">淘</span></span>
                  <span>1件价格 <span className="text-[#ff5000] font-semibold">¥0.8</span></span>
                  <span>官方仓退货</span>
                </div>
                <div className="flex items-center gap-2">
                  <button className="border border-[#ff5000] text-[#ff5000] px-3 py-1 rounded-sm text-[12px] hover:bg-[#fff8f6]">立即铺货</button>
                  <button className="border border-[#ff5000] text-[#ff5000] px-3 py-1 rounded-sm text-[12px] hover:bg-[#fff8f6]">加铺货单</button>
                  <button className="border border-[#ff5000] text-[#ff5000] px-3 py-1 rounded-sm text-[12px] hover:bg-[#fff8f6]">代发下单</button>
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* ==================== 底部 Tab 导航区 ==================== */}
        <div className="mt-6 border-b border-gray-200">
          <div className="flex items-center gap-8 px-6">
            <button className="py-4 text-[16px] font-medium text-gray-900 border-b-2 border-gray-900">
              商品评价
            </button>
            <button className="py-4 text-[16px] text-gray-600 hover:text-gray-900 transition-colors border-b-2 border-transparent">
              商品属性
            </button>
            <button className="py-4 text-[16px] text-gray-600 hover:text-gray-900 transition-colors border-b-2 border-transparent">
              包装信息
            </button>
            <button className="py-4 text-[16px] text-gray-600 hover:text-gray-900 transition-colors border-b-2 border-transparent">
              商品详情
            </button>
            <button className="py-4 text-[16px] text-gray-600 hover:text-gray-900 transition-colors border-b-2 border-transparent">
              热门推荐
            </button>
          </div>
        </div>
      </main>

      {/* 定义一个极细的滚动条样式，用于 SKU 列表 */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #f1f1f1; 
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #d1d5db; 
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #9ca3af; 
        }
      `}</style>
    </div>
  );
}
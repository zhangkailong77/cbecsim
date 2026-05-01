import { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

type OrderType = 'placed' | 'confirmed';

interface ShopFlashSaleDataViewProps {
  runId: number | null;
  campaignId: number | null;
  readOnly?: boolean;
  onBackToFlashSale: () => void;
}

interface FlashSaleDataOverview {
  campaign: {
    id: number;
    name: string;
    status: string;
    status_label: string;
    edit_period_label: string;
    activity_period_label: string;
    item_count: number;
  };
  order_type: OrderType;
  metrics: {
    reminder_count: number;
    product_view_count: number;
    product_click_count: number;
    ctr: number;
    sales_amount: number;
    order_count: number;
    unit_count: number;
    buyer_count: number;
  };
}

interface FlashSaleRankingVariation {
  campaign_item_id: number;
  variant_id: number | null;
  variation_name: string;
  activity_stock: number;
  flash_price: number;
  sales_amount: number;
  order_count: number;
  unit_count: number;
}

interface FlashSaleRankingItem {
  listing_id: number;
  item_id_label: string;
  name: string;
  image_url: string | null;
  sales_amount: number;
  order_count: number;
  unit_count: number;
  variations: FlashSaleRankingVariation[];
}

// ---------------- 图标与悬浮提示组件 ----------------
const InfoIcon = ({ tooltipText }: { tooltipText?: string }) => {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const iconRef = useRef<HTMLDivElement>(null);

  const handleMouseEnter = () => {
    if (!tooltipText || !iconRef.current) return;
    // 获取图标在当前屏幕上的绝对坐标
    const rect = iconRef.current.getBoundingClientRect();
    setPos({
      x: rect.left + rect.width / 2,
      y: rect.top - 8 // 向上偏移 8px，给小三角留出空间
    });
    setShow(true);
  };

  const iconSvg = (
    <svg viewBox="0 0 1024 1024" className={`w-3.5 h-3.5 fill-current transition-colors ${tooltipText && show ? 'text-[#ee4d2d]' : 'text-[#b2b2b2]'}`}>
      <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path>
      <path d="M464 688h96v-96h-96v96zm48-392c-65.3 0-118.3 49.3-126.9 113.1l74 15.6c4.5-33.6 34.3-56.7 60.9-56.7 34.1 0 64 25.1 64 60 0 25.5-16.7 44.5-44.1 61.2l-23.9 14.6V560h80v-34.5l22.4-13.6c39-23.7 61.6-58.1 61.6-99.9 0-64-57.3-116-128-116z"></path>
    </svg>
  );

  if (!tooltipText) return <span className="inline-block ml-1">{iconSvg}</span>;

  return (
    <>
      <div 
        ref={iconRef}
        className="inline-flex items-center cursor-pointer ml-1.5"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setShow(false)}
      >
        {iconSvg}
      </div>
      
      {/* 使用 fixed 定位，使其相对于整个浏览器窗口渲染，彻底跳出溢出隐藏的限制 */}
      {show && (
        <div 
          className="fixed z-[9999] w-max max-w-[280px] bg-white border border-[#ebebeb] shadow-[0_4px_16px_rgba(0,0,0,0.12)] rounded-sm px-4 py-3 text-[12px] text-[#555] font-normal whitespace-normal leading-relaxed pointer-events-none transform -translate-x-1/2 -translate-y-full text-left"
          style={{ left: pos.x, top: pos.y }}
        >
          {tooltipText}
          <div className="absolute -bottom-[5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-white border-b border-r border-[#ebebeb] transform rotate-45"></div>
        </div>
      )}
    </>
  );
};

const ExportIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
    <polyline points="7 10 12 15 17 10"></polyline>
    <line x1="12" y1="15" x2="12" y2="3"></line>
  </svg>
);

const ChevronRightIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-[#05a]">
    <polyline points="9 18 15 12 9 6"></polyline>
  </svg>
);

const SortIcon = () => (
  <div className="inline-flex flex-col ml-1 w-2 cursor-pointer opacity-40 hover:opacity-100">
    <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="3" fill="none" className="-mb-[3px]"><polyline points="18 15 12 9 6 15"></polyline></svg>
    <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="3" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
  </div>
);

const ShieldIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00bfa5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    <polyline points="9 12 11 14 15 10"></polyline>
  </svg>
);

export default function ShopFlashSaleDataView({ runId, campaignId, readOnly = false, onBackToFlashSale }: ShopFlashSaleDataViewProps) {
  const [isOrderTypeOpen, setIsOrderTypeOpen] = useState(false);
  const [selectedOrderType, setSelectedOrderType] = useState<OrderType>('confirmed');
  const [overview, setOverview] = useState<FlashSaleDataOverview | null>(null);
  const [rankingData, setRankingData] = useState<FlashSaleRankingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [rankingLoading, setRankingLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const orderTypeOptions: Array<{ label: string; value: OrderType }> = [
    { label: '已下单', value: 'placed' },
    { label: '已确认订单', value: 'confirmed' },
  ];
  const selectedOrderTypeLabel = orderTypeOptions.find((option) => option.value === selectedOrderType)?.label || '已确认订单';

  // 指标滚动相关状态与逻辑
  const metricsScrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScrollState = () => {
    if (metricsScrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = metricsScrollRef.current;
      setCanScrollLeft(scrollLeft > 0);
      // 加1个像素的容差，防止因为缩放带来的浮点数计算误差
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1);
    }
  };

  useEffect(() => {
    checkScrollState();
    window.addEventListener('resize', checkScrollState);
    return () => window.removeEventListener('resize', checkScrollState);
  }, []);

  const handleScroll = (direction: 'left' | 'right') => {
    if (metricsScrollRef.current) {
      const clientWidth = metricsScrollRef.current.clientWidth;
      const scrollAmount = direction === 'left' ? -clientWidth : clientWidth;
      metricsScrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    if (!runId || !campaignId) {
      setError('缺少限时抢购活动 ID');
      setOverview(null);
      setRankingData([]);
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('请先登录');
      return;
    }
    let cancelled = false;
    const loadOverview = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ order_type: selectedOrderType });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/campaigns/${campaignId}/data?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error(response.status === 404 ? '未找到该限时抢购活动' : '限时抢购数据加载失败');
        const data = (await response.json()) as FlashSaleDataOverview;
        if (!cancelled) setOverview(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '限时抢购数据加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    const loadRanking = async () => {
      setRankingLoading(true);
      try {
        const params = new URLSearchParams({ order_type: selectedOrderType, sort_by: 'sales_amount', sort_order: 'desc' });
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/flash-sale/campaigns/${campaignId}/data/products?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('商品排名加载失败');
        const data = (await response.json()) as { items: FlashSaleRankingItem[] };
        if (!cancelled) setRankingData(data.items || []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '商品排名加载失败');
      } finally {
        if (!cancelled) setRankingLoading(false);
      }
    };
    void loadOverview();
    void loadRanking();
    return () => {
      cancelled = true;
    };
  }, [runId, campaignId, selectedOrderType]);

  const formatCurrency = (value: number) => `RM ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const metrics = overview?.metrics;
  const averageOrderValue = metrics && metrics.buyer_count > 0 ? metrics.sales_amount / metrics.buyer_count : 0;

  const keyMetrics = [
    {
      label: '提醒设置数',
      value: String(metrics?.reminder_count ?? 0),
      tooltip: '访客点击此店铺限时抢购活动“提醒我”按钮的总次数'
    },
    {
      label: '商品浏览量',
      value: String(metrics?.product_view_count ?? 0),
      tooltip: '此店铺限时抢购活动中商品卡片被浏览的总次数'
    },
    {
      label: '商品点击数',
      value: String(metrics?.product_click_count ?? 0),
      tooltip: '此店铺限时抢购活动中商品卡片被点击的总次数'
    },
    {
      label: '点击率 (CTR)',
      value: `${(metrics?.ctr ?? 0).toFixed(2)} %`,
      tooltip: '此店铺限时抢购活动中商品卡片的总点击次数除以总浏览次数'
    },
    {
      label: '销售额',
      value: formatCurrency(metrics?.sales_amount ?? 0),
      tooltip: '包含此店铺限时抢购商品的已确认订单总价值（不含其他促销折扣），反映卖家在扣除卖家返现后实际收到的销售金额'
    },
    {
      label: '订单数',
      value: String(metrics?.order_count ?? 0),
      tooltip: '包含此店铺限时抢购商品的已确认订单总数'
    },
    {
      label: '买家数',
      value: String(metrics?.buyer_count ?? 0),
      tooltip: '包含此店铺限时抢购商品的已确认订单的唯一买家总数'
    },
    {
      label: '客单价',
      value: formatCurrency(averageOrderValue),
      tooltip: '此店铺限时抢购活动的销售额除以买家数'
    },
  ];

  // 统一定义商品表格的列宽 (8列)
  const gridCols = "grid-cols-[60px_2.5fr_1.8fr_1fr_1fr_1fr_1fr_1fr]";

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-8 py-6 custom-scrollbar text-[#333]">
      <div className="mx-auto max-w-[1360px]">
        
        {readOnly && (
          <div className="mb-4 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览数据页，但无法执行数据导出操作。
          </div>
        )}

        {error && (
          <div className="mb-4 border border-red-200 bg-red-50 px-4 py-2 text-[13px] text-red-600">
            {error}
          </div>
        )}

        {loading && (
          <div className="mb-4 border border-[#ebebeb] bg-white px-4 py-2 text-[13px] text-[#666]">
            正在加载限时抢购数据...
          </div>
        )}

        {/* 广告 Banner 占位 */}
        <div className="bg-[#e9fbf8] border border-[#b4efe5] rounded-sm px-6 py-4 mb-4 flex items-center justify-between">
          <div className="flex items-center text-[15px] font-medium text-[#113a34]">
            <ShieldIcon />
            <span className="text-[#00bfa5] mr-1">享受 ROAS 保护服务</span> 使用 GMV Max 自定义 ROAS 商品广告
          </div>
          <button className="bg-[#00bfa5] text-white px-4 py-1.5 rounded-sm text-[13px] hover:bg-[#00a891]">
            查看详情 &gt;
          </button>
        </div>

        {/* 1. 基础信息卡片 */}
        <section className="bg-white px-6 py-6 shadow-sm border border-[#ebebeb] rounded-sm mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <h2 className="text-[20px] font-medium text-[#333] mr-4">我的店铺限时抢购数据详情</h2>
              <button className="text-[14px] text-[#05a] flex items-center hover:underline" onClick={onBackToFlashSale}>
                查看活动详情 <ChevronRightIcon />
              </button>
            </div>
            
            <div className="flex items-center gap-4">
              {/* 订单类型下拉菜单 */}
              <div className="text-[13px] text-[#666] flex items-center relative">
                订单类型 <InfoIcon />
                <div 
                  className={`ml-2 border px-3 py-1.5 rounded-sm text-[#333] cursor-pointer bg-white flex items-center justify-between min-w-[130px] transition-colors ${isOrderTypeOpen ? 'border-[#ee4d2d]' : 'border-[#d9d9d9]'}`}
                  onClick={() => setIsOrderTypeOpen(!isOrderTypeOpen)}
                >
                  <span>{selectedOrderTypeLabel}</span>
                  {isOrderTypeOpen ? (
                    <ChevronUp size={14} className="text-[#999] ml-2" />
                  ) : (
                    <ChevronDown size={14} className="text-[#999] ml-2" />
                  )}
                </div>

                {/* 下拉面板 */}
                {isOrderTypeOpen && (
                  <div className="absolute top-[calc(100%+4px)] right-0 w-[130px] bg-white border border-[#ebebeb] shadow-[0_4px_12px_rgba(0,0,0,0.08)] rounded-sm py-1.5 z-20">
                    {orderTypeOptions.map((type) => (
                      <div
                        key={type.value}
                        className={`px-4 py-2 cursor-pointer transition-colors ${selectedOrderType === type.value ? 'text-[#ee4d2d]' : 'text-[#333] hover:bg-[#fafafa]'}`}
                        onClick={() => {
                          setSelectedOrderType(type.value);
                          setIsOrderTypeOpen(false);
                        }}
                      >
                        {type.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button className="flex items-center border border-[#d9d9d9] bg-white px-4 py-1.5 rounded-sm text-[13px] text-[#333] hover:bg-[#fafafa]">
                <ExportIcon /> 导出数据
              </button>
            </div>
          </div>

          {/* 状态时间栏 */}
          <div className="mt-6 bg-[#fafafa] border border-[#ebebeb] px-4 py-3 text-[12px] text-[#666] flex items-center gap-6 rounded-sm">
            <div className="flex items-center">
              状态：<span className="bg-[#e6e6e6] text-[#999] px-2 py-0.5 rounded-sm ml-1 leading-tight">{overview?.campaign.status_label || '-'}</span>
            </div>
            <div>
              编辑期：<span className="text-[#333]">{overview?.campaign.edit_period_label || '-'}</span>
            </div>
            <div>
              活动期：<span className="text-[#333]">{overview?.campaign.activity_period_label || '-'}</span>
            </div>
          </div>
        </section>

        {/* 2. 关键指标 (Key Metrics) - 带横向滚动 */}
        <section className="bg-white px-6 py-6 shadow-sm border border-[#ebebeb] rounded-sm mb-4">
          <h2 className="text-[18px] font-medium text-[#333] mb-4">关键指标</h2>
          
          <div className="relative border border-[#ebebeb] rounded-sm bg-white group/slider">
            {/* 隐藏原生滚动条的滚动容器 */}
            <div 
              ref={metricsScrollRef} 
              onScroll={checkScrollState}
              className="flex overflow-x-auto scroll-smooth [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
            >
              {keyMetrics.map((item, index) => (
                <div 
                  key={item.label} 
                  // 强制每个块占用总宽度的 1/6 (一屏展示6个)
                  className={`flex-[0_0_16.666667%] p-5 border-r border-[#ebebeb] ${index === keyMetrics.length - 1 ? 'border-r-0' : ''}`}
                >
                  <div className="text-[13px] text-[#666] flex items-center">
                    {item.label} 
                    <InfoIcon tooltipText={item.tooltip} />
                  </div>
                  <div className="mt-3 text-[22px] font-medium text-[#333] truncate">{item.value}</div>
                </div>
              ))}
            </div>

            {/* 左侧浮动箭头 */}
            {canScrollLeft && (
              <button 
                onClick={() => handleScroll('left')}
                className="absolute left-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-[#e6e6e6] hover:bg-[#d4d4d4] flex items-center justify-center text-white shadow-sm z-10"
              >
                <ChevronLeft size={16} strokeWidth={3} />
              </button>
            )}

            {/* 右侧浮动箭头 */}
            {canScrollRight && (
              <button 
                onClick={() => handleScroll('right')}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-[#e6e6e6] hover:bg-[#d4d4d4] flex items-center justify-center text-white shadow-sm z-10"
              >
                <ChevronRight size={16} strokeWidth={3} />
              </button>
            )}
          </div>
        </section>

        {/* 3. 商品表现 / 排名 (Product Ranking) */}
        <section className="bg-white px-6 py-6 shadow-sm border border-[#ebebeb] rounded-sm">
          <h2 className="text-[18px] font-medium text-[#333] mb-4">商品排名</h2>
          
          <div className="border border-[#ebebeb] rounded-sm">
            {/* 表头 */}
            <div className={`grid ${gridCols} bg-[#fafafa] border-b border-[#ebebeb] px-5 py-3 text-[13px] text-[#999] font-medium items-center`}>
              <div className="text-center">排名</div>
              <div>商品</div>
              <div className="truncate min-w-0 pr-2">变体</div>
              <div className="truncate min-w-0 pr-2">活动库存</div>
              <div className="truncate min-w-0 pr-2">折后价</div>
              <div className="flex items-center cursor-pointer hover:text-[#333]">销售额 <SortIcon /></div>
              <div className="flex items-center cursor-pointer hover:text-[#333]">订单数 <SortIcon /></div>
              <div className="flex items-center cursor-pointer hover:text-[#333]">件数 <SortIcon /></div>
            </div>

            {/* 表格主体 */}
            <div>
              {rankingLoading ? (
                <div className="px-5 py-16 text-center text-[13px] text-[#999]">
                  正在加载商品排名...
                </div>
              ) : rankingData.length > 0 ? (
                rankingData.map((item, index) => (
                  <div key={item.listing_id} className="border-b border-[#ebebeb] last:border-b-0">
                    
                    {/* 主商品汇总行 (Parent Row) */}
                    <div className={`grid ${gridCols} px-5 py-4 items-center`}>
                      <div className="text-center text-[14px] text-[#999] font-medium">{index + 1}</div>
                      <div className="flex items-center gap-3 pr-4 min-w-0">
                        <div className="w-12 h-12 bg-[#f0f0f0] border border-[#e5e5e5] rounded-[2px] flex-shrink-0 bg-cover bg-center" style={{ backgroundImage: item.image_url ? `url(${item.image_url})` : undefined }}></div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] text-[#333] font-medium truncate" title={item.name}>
                            {item.name}
                          </div>
                          <div className="text-[12px] text-[#999] mt-0.5 truncate">
                            Item ID: {item.item_id_label}
                          </div>
                        </div>
                      </div>
                      <div className="text-[13px] text-[#666] truncate min-w-0 pr-4">总计</div>
                      <div className="text-[13px] text-[#999]">-</div>
                      <div className="text-[13px] text-[#999]">-</div>
                      <div className="text-[13px] text-[#333]">{formatCurrency(item.sales_amount)}</div>
                      <div className="text-[13px] text-[#333]">{item.order_count}</div>
                      <div className="text-[13px] text-[#333]">{item.unit_count}</div>
                    </div>

                    {/* 变体拆解行 (Child Rows) */}
                    <div className="pb-3">
                      {item.variations.map((variant, vIdx) => (
                        <div key={vIdx} className={`grid ${gridCols} px-5 py-2.5 items-center hover:bg-[#fafafa] transition-colors`}>
                          <div></div> {/* 排名列留空 */}
                          <div></div> {/* 主商品列留空 */}
                          <div 
                            className="text-[13px] text-[#666] truncate min-w-0 pr-4" 
                            title={variant.variation_name}
                          >
                            {variant.variation_name}
                          </div>
                          <div className="text-[13px] text-[#666]">{variant.activity_stock}</div>
                          <div className="text-[13px] text-[#666]">{formatCurrency(variant.flash_price)}</div>
                          <div className="text-[13px] text-[#666]">{formatCurrency(variant.sales_amount)}</div>
                          <div className="text-[13px] text-[#666]">{variant.order_count}</div>
                          <div className="text-[13px] text-[#666]">{variant.unit_count}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="px-5 py-16 text-center text-[13px] text-[#999]">
                  暂无商品表现数据
                </div>
              )}
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
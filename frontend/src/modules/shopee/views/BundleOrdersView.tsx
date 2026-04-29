import { SlidersHorizontal, HelpCircle, Download } from 'lucide-react';
import { useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface BundleOrdersViewProps {
  runId: number | null;
  campaignId: number | null;
}

interface BundleOrderItem {
  id: string;
  imageUrl: string | null;
  name: string;
  sku: string | null;
  variation: string;
  priceCurrent: number;
  qty: number;
}

interface BundleOrderRow {
  id: string;
  status: string;
  subtotalCurrent: number;
  subtotalOriginal: number | null;
  items: BundleOrderItem[];
}

interface BundleDataRow {
  date: string;
  sales: number;
  orders: number;
  bundles: number;
  units: number;
  buyers: number;
  salesPerBuyer: number;
}

interface BundleOrdersResponse {
  campaign_name: string;
  status_label: string;
  start_at: string | null;
  end_at: string | null;
  purchase_limit: number | null;
  bundle_type_label: string;
  bundle_rule_text: string;
  data_period_text: string;
  order_count: number;
  metric_cards: {
    sales: number;
    orders: number;
    bundles: number;
    units: number;
    buyers: number;
    salesPerBuyer: number;
  };
  orders: BundleOrderRow[];
  data_rows: BundleDataRow[];
}

function formatMoney(value: number | null | undefined) {
  return Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

const PAGE_SIZE = 10;

export default function BundleOrdersView({ runId, campaignId }: BundleOrdersViewProps) {
  // 控制当前显示的 Tab：'orders' (订单概览) 或 'data' (数据详情)
  const [activeTab, setActiveTab] = useState<'orders' | 'data'>('orders');
  const [data, setData] = useState<BundleOrdersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState('1');

  useEffect(() => {
    if (!runId || !campaignId) {
      setError('缺少活动信息，无法加载订单。');
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('登录状态失效，请重新登录。');
      return;
    }
    let cancelled = false;
    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/bundle/campaigns/${campaignId}/orders`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('load failed');
        const result = (await response.json()) as BundleOrdersResponse;
        if (!cancelled) setData(result);
      } catch {
        if (!cancelled) setError('套餐优惠订单数据加载失败，请稍后重试。');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void loadData();
    return () => {
      cancelled = true;
    };
  }, [campaignId, runId]);

  const orders = data?.orders ?? [];
  const dataRows = data?.data_rows ?? [];
  const metrics = data?.metric_cards;
  const totalItems = activeTab === 'orders' ? orders.length : dataRows.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageStart = (safeCurrentPage - 1) * PAGE_SIZE;
  const visibleOrders = orders.slice(pageStart, pageStart + PAGE_SIZE);
  const visibleDataRows = dataRows.slice(pageStart, pageStart + PAGE_SIZE);
  const pageNumbers = Array.from({ length: totalPages }, (_, idx) => idx + 1).filter((page) =>
    page === 1 || page === totalPages || Math.abs(page - safeCurrentPage) <= 2
  );

  useEffect(() => {
    setCurrentPage(1);
    setPageInput('1');
  }, [activeTab, campaignId]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
      setPageInput(String(totalPages));
    }
  }, [currentPage, totalPages]);

  const goToPage = (page: number) => {
    const nextPage = Math.min(Math.max(page, 1), totalPages);
    setCurrentPage(nextPage);
    setPageInput(String(nextPage));
  };

  const confirmPageInput = () => {
    const page = Number.parseInt(pageInput, 10);
    if (!Number.isNaN(page)) {
      goToPage(page);
    } else {
      setPageInput(String(safeCurrentPage));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-8 py-8 custom-scrollbar">
      <div className="mx-auto max-w-[1360px] pb-20">
        
        {/* --- 基本信息卡片 --- */}
        <section className="rounded-[3px] border border-[#e5e5e5] bg-white shadow-sm mb-4">
          <div className="flex items-center gap-3 border-b border-[#f0f0f0] px-6 py-4">
            <h2 className="text-[18px] font-medium text-[#333]">基本信息</h2>
            <span className="rounded-[2px] bg-[#f4f4f4] px-1.5 py-0.5 text-[12px] text-[#999]">{data?.status_label || '-'}</span>
          </div>
          <div className="px-6 py-6 text-[13px] text-[#333]">
            <div className="flex flex-wrap gap-y-5">
              <div className="w-[33%]">
                <span className="text-[#999]">套餐优惠名称：</span>{data?.campaign_name || '-'}
              </div>
              <div className="w-[34%]">
                <span className="text-[#999]">活动时间：</span>{data?.start_at || '-'} - {data?.end_at || '-'}
              </div>
              <div className="w-[33%]">
                <span className="text-[#999]">购买限制：</span>{data?.purchase_limit ? `每位买家 ${data.purchase_limit} 个套餐` : '-'}
              </div>
              <div className="w-[100%]">
                <span className="text-[#999]">套餐优惠类型：</span>{data?.bundle_rule_text || '-'}
              </div>
            </div>
          </div>
        </section>

        {/* --- 主体卡片区 --- */}
        <section className="rounded-[3px] border border-[#e5e5e5] bg-white shadow-sm">
          {/* 选项卡切换 */}
          <div className="flex border-b border-[#e5e5e5] px-6 pt-2">
            <div 
              onClick={() => setActiveTab('orders')}
              className={`py-3 text-[15px] cursor-pointer mr-8 ${activeTab === 'orders' ? 'border-b-2 border-[#ee4d2d] font-medium text-[#ee4d2d]' : 'text-[#333] hover:text-[#ee4d2d]'}`}
            >
              套餐优惠订单概览
            </div>
            <div 
              onClick={() => setActiveTab('data')}
              className={`py-3 text-[15px] cursor-pointer ${activeTab === 'data' ? 'border-b-2 border-[#ee4d2d] font-medium text-[#ee4d2d]' : 'text-[#333] hover:text-[#ee4d2d]'}`}
            >
              套餐数据详情
            </div>
          </div>

          {/* ================= 视图 1：订单概览 ================= */}
          {activeTab === 'orders' && (
            <>
              {/* 顶部操作栏 */}
              <div className="flex items-center justify-between px-6 py-4">
                <div className="text-[13px] text-[#999]">
                  <span className="text-[#333] font-medium mr-1">{data?.order_count ?? 0}</span>个订单 (v2)
                </div>
                <div className="flex items-center gap-3">
                  <button className="h-8 rounded-[3px] border border-[#d9d9d9] bg-white px-4 text-[13px] text-[#555] transition-colors hover:bg-[#f5f5f5]">
                    导出
                  </button>
                </div>
              </div>

              {/* 订单表格 */}
              <div className="px-6 pb-6">
                <table className="w-full border-collapse text-left text-[13px]">
                  <thead>
                    <tr className="bg-[#fafafa] text-[#999]">
                      <th className="w-[45%] py-3 pl-4 font-normal border-y border-[#e5e5e5]">商品</th>
                      <th className="w-[15%] py-3 font-normal text-center border-y border-[#e5e5e5]">单价</th>
                      <th className="w-[10%] py-3 font-normal text-center border-y border-[#e5e5e5]">数量</th>
                      <th className="w-[15%] py-3 font-normal text-center border-y border-[#e5e5e5]">小计</th>
                      <th className="w-[15%] py-3 pr-4 font-normal text-center border-y border-[#e5e5e5]">订单状态</th>
                    </tr>
                  </thead>

                  {error ? (
                    <tbody>
                      <tr><td colSpan={5} className="border border-[#e5e5e5] py-6 text-center text-[#d63b1f]">{error}</td></tr>
                    </tbody>
                  ) : null}
                  {!data && !error && !loading ? (
                    <tbody>
                      <tr><td colSpan={5} className="border border-[#e5e5e5] py-6 text-center text-[#999]">请选择套餐优惠活动。</td></tr>
                    </tbody>
                  ) : null}
                  {loading ? (
                    <tbody>
                      <tr><td colSpan={5} className="border border-[#e5e5e5] py-6 text-center text-[#999]">订单数据加载中...</td></tr>
                    </tbody>
                  ) : null}
                  {data && orders.length === 0 && !loading && !error ? (
                    <tbody>
                      <tr><td colSpan={5} className="border border-[#e5e5e5] py-12 text-center text-[#999]">暂无订单数据</td></tr>
                    </tbody>
                  ) : null}
                  {visibleOrders.map((order) => (
                    <tbody key={order.id}>
                      <tr><td colSpan={5} className="h-4"></td></tr>
                      <tr className="bg-[#fafafa] border border-[#e5e5e5]">
                        <td colSpan={5} className="py-2.5 px-4 text-[13px] text-[#333]">
                          订单编号 : {order.id}
                        </td>
                      </tr>
                      {order.items.map((item, itemIdx) => (
                        <tr 
                          key={item.id} 
                          className={`border-l border-r border-[#e5e5e5] ${itemIdx === order.items.length - 1 ? 'border-b' : ''}`}
                        >
                          <td className="p-4 align-middle">
                            <div className="flex items-start gap-3">
                              {item.imageUrl ? (
                                <img src={item.imageUrl} alt="" className="h-[60px] w-[60px] flex-shrink-0 border border-[#e5e5e5] object-cover" />
                              ) : (
                                <div className="flex h-[60px] w-[60px] flex-shrink-0 items-center justify-center border border-[#e5e5e5] bg-[#f6f6f6] text-[11px] text-[#999]">图</div>
                              )}
                              <div>
                                <div className="text-[13px] text-[#333] line-clamp-2 leading-tight">{item.name}</div>
                                <div className="mt-1.5 text-[12px] text-[#999]">规格: {item.variation}</div>
                                <div className="mt-0.5 text-[12px] text-[#999]">SKU: {item.sku}</div>
                              </div>
                            </div>
                          </td>
                          <td className="align-middle text-center py-4 text-[#333]">RM {formatMoney(item.priceCurrent)}</td>
                          <td className="align-middle text-center py-4 text-[#555]">{item.qty}</td>
                          {itemIdx === 0 && (
                            <>
                              <td rowSpan={order.items.length} className="align-middle text-center p-4 border-l border-[#e5e5e5]">
                                <div className="text-[#333]">RM {formatMoney(order.subtotalCurrent)}</div>
                                {order.subtotalOriginal && <div className="text-[#999] line-through mt-0.5 text-[12px]">RM {formatMoney(order.subtotalOriginal)}</div>}
                              </td>
                              <td rowSpan={order.items.length} className="align-middle text-center p-4 text-[#333] border-l border-[#e5e5e5]">
                                {order.status}
                              </td>
                            </>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  ))}
                </table>
              </div>
            </>
          )}

          {/* ================= 视图 2：数据详情 ================= */}
          {activeTab === 'data' && (
            <div className="px-6 py-6">
              
              {/* 头部信息与导出按钮 */}
              <div className="flex items-center justify-between mb-4">
                <div className="text-[13px] text-[#555]">
                  数据时间段: {data?.data_period_text || '-'}
                </div>
                <button className="flex h-8 items-center gap-2 rounded-[3px] border border-[#d9d9d9] bg-white px-3 text-[13px] text-[#555] transition-colors hover:bg-[#f5f5f5]">
                  <Download size={14} />
                  导出数据
                </button>
              </div>

              {/* 6列数据概览网格 */}
              <div className="grid grid-cols-6 border border-[#e5e5e5] rounded-[3px] mb-8">
                {[
                  { label: '销售额', value: `RM ${formatMoney(metrics?.sales)}` },
                  { label: '订单数', value: formatMoney(metrics?.orders) },
                  { label: '已订购套餐数', value: formatMoney(metrics?.bundles) },
                  { label: '已售件数', value: formatMoney(metrics?.units) },
                  { label: '买家数', value: formatMoney(metrics?.buyers) },
                  { label: '每位买家销售额', value: `RM ${formatMoney(metrics?.salesPerBuyer)}` },
                ].map((item, idx) => (
                  <div key={item.label} className={`py-5 pl-5 ${idx !== 5 ? 'border-r border-[#f0f0f0]' : ''}`}>
                    <div className="flex items-center gap-1 text-[13px] text-[#555] mb-2">
                      {item.label}
                      <HelpCircle size={13} className="text-[#ccc]" />
                    </div>
                    <div className="text-[22px] font-bold text-[#333]">{item.value}</div>
                  </div>
                ))}
              </div>

              {/* 数据详情表格 */}
              <h3 className="text-[16px] font-medium text-[#333] mb-4">数据详情</h3>
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="bg-[#fafafa] text-[#999] border-y border-[#e5e5e5]">
                    <th className="py-3 pl-4 font-normal">日期</th>
                    <th className="py-3 pr-4 font-normal text-right">销售额</th>
                    <th className="py-3 pr-4 font-normal text-right">订单数</th>
                    <th className="py-3 pr-4 font-normal text-right">已订购套餐数</th>
                    <th className="py-3 pr-4 font-normal text-right">已售件数</th>
                    <th className="py-3 pr-4 font-normal text-right">买家数</th>
                    <th className="py-3 pr-4 font-normal text-right">每位买家销售额</th>
                  </tr>
                </thead>
                <tbody>
                  {dataRows.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-[#999]">暂无数据详情</td>
                    </tr>
                  ) : null}
                  {visibleDataRows.map((row, idx) => (
                    <tr key={row.date} className={`border-b border-[#f1f1f1] ${idx % 2 === 0 ? 'bg-white' : 'bg-[#fafafa]'}`}>
                      <td className="py-4 pl-4 text-[#333]">{row.date}</td>
                      <td className="py-4 pr-4 text-right text-[#555]">RM {formatMoney(row.sales)}</td>
                      <td className="py-4 pr-4 text-right text-[#555]">{row.orders}</td>
                      <td className="py-4 pr-4 text-right text-[#555]">{row.bundles}</td>
                      <td className="py-4 pr-4 text-right text-[#555]">{row.units}</td>
                      <td className="py-4 pr-4 text-right text-[#555]">{row.buyers}</td>
                      <td className="py-4 pr-4 text-right text-[#555]">RM {formatMoney(row.salesPerBuyer)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 公共分页组件 (两个 Tab 共用底部) */}
          <div className="flex items-center justify-end gap-4 border-t border-[#e5e5e5] px-6 py-5 text-[13px] text-[#555]">
            <div className="flex items-center gap-1">
              <button onClick={() => goToPage(safeCurrentPage - 1)} disabled={safeCurrentPage <= 1} className={`flex h-7 w-7 items-center justify-center ${safeCurrentPage <= 1 ? 'cursor-not-allowed text-[#ccc]' : 'hover:text-[#ee4d2d]'}`}>{'<'}</button>
              {pageNumbers.map((page, idx) => (
                <div key={page} className="flex items-center gap-1">
                  {idx > 0 && page - pageNumbers[idx - 1] > 1 ? <span className="px-1 text-[#999]">...</span> : null}
                  <button onClick={() => goToPage(page)} className={`flex h-7 w-7 items-center justify-center ${page === safeCurrentPage ? 'text-[#ee4d2d]' : 'hover:text-[#ee4d2d]'}`}>{page}</button>
                </div>
              ))}
              <button onClick={() => goToPage(safeCurrentPage + 1)} disabled={safeCurrentPage >= totalPages} className={`flex h-7 w-7 items-center justify-center ${safeCurrentPage >= totalPages ? 'cursor-not-allowed text-[#ccc]' : 'hover:text-[#ee4d2d]'}`}>{'>'}</button>
            </div>
            <div className="ml-2 flex items-center gap-2">
              <span>前往</span>
              <input
                type="text"
                value={pageInput}
                onChange={(event) => setPageInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') confirmPageInput();
                }}
                className="h-7 w-12 rounded-[2px] border border-[#d9d9d9] text-center outline-none focus:border-[#ee4d2d]"
              />
              <span>页</span>
              <button onClick={confirmPageInput} className="ml-2 h-7 rounded-[2px] border border-[#d9d9d9] bg-white px-4 hover:bg-[#f5f5f5]">
                确认
              </button>
            </div>
          </div>

        </section>
      </div>
    </div>
  );
}
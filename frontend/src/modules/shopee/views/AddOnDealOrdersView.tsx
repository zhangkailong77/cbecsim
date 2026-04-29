import { useEffect, useState } from 'react';
import { HelpCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface AddOnDealOrdersViewProps {
  campaignId: number | null;
  runId: number | null;
  onBackToDiscount: () => void;
}

interface AddOnDealOrderItem {
  id: string;
  type: string;
  imageUrl: string | null;
  name: string;
  sku: string | null;
  variation: string;
  priceCurrent: number;
  priceOriginal: number | null;
  qty: number;
}

interface AddOnDealOrderRow {
  id: string;
  status: string;
  subtotalCurrent: number;
  subtotalOriginal: number | null;
  items: AddOnDealOrderItem[];
}

interface AddOnDealOrdersResponse {
  campaign_name: string;
  promotion_type_label: string;
  status_label: string;
  start_at: string | null;
  end_at: string | null;
  addon_purchase_limit: number | null;
  gift_min_spend: number | null;
  orders: AddOnDealOrderRow[];
}

function formatMoney(value: number | null | undefined) {
  return Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function formatDateTime(value: string | null) {
  if (!value) return '-';
  const [datePart, timePart = ''] = value.split('T');
  const [year, month, day] = datePart.split('-');
  return year && month && day ? `${day}-${month}-${year} ${timePart}`.trim() : value;
}

export default function AddOnDealOrdersView({ campaignId, runId }: AddOnDealOrdersViewProps) {
  const [data, setData] = useState<AddOnDealOrdersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
        const response = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/add-on/campaigns/${campaignId}/orders`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('load failed');
        const result = (await response.json()) as AddOnDealOrdersResponse;
        if (!cancelled) setData(result);
      } catch {
        if (!cancelled) setError('订单数据加载失败，请稍后重试。');
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

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-8 py-8 custom-scrollbar">
      <div className="mx-auto max-w-[1360px] pb-20">
        
        {/* --- 基本信息卡片 --- */}
        <section className="rounded-[3px] border border-[#e5e5e5] bg-white shadow-sm">
          <div className="flex items-center gap-3 border-b border-[#f0f0f0] px-6 py-4">
            <h2 className="text-[18px] font-medium text-[#333]">基本信息</h2>
            <span className="rounded-[2px] bg-[#f4f4f4] px-1.5 py-0.5 text-[12px] text-[#999]">{data?.status_label || '-'}</span>
          </div>
          <div className="px-6 py-6 text-[13px] text-[#333]">
            <div className="flex flex-wrap gap-y-6">
              <div className="w-[30%]">
                <span className="text-[#999]">促销类型：</span>{data?.promotion_type_label || '-'}
              </div>
              <div className="w-[35%] flex items-center gap-1">
                <span className="text-[#999]">活动名称</span>
                <HelpCircle size={14} className="text-[#ccc] mr-1" />
                <span>：{data?.campaign_name || '-'}</span>
              </div>
              <div className="w-[35%]">
                <span className="text-[#999]">活动时间：</span>{formatDateTime(data?.start_at || null)} - {formatDateTime(data?.end_at || null)}
              </div>
              <div className="w-[100%] flex items-center gap-1">
                <span className="text-[#999]">加价购商品限购数量</span>
                <HelpCircle size={14} className="text-[#ccc] mr-1" />
                <span>：{data?.addon_purchase_limit ?? '-'}</span>
              </div>
            </div>
          </div>
        </section>

        {/* --- 订单概览卡片 --- */}
        <section className="mt-4 rounded-[3px] border border-[#e5e5e5] bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-[#f0f0f0] px-6 py-4">
            <h2 className="text-[18px] font-medium text-[#333]">订单概览</h2>
            <div className="flex items-center gap-3">
              <button className="h-8 rounded-[3px] border border-[#d9d9d9] bg-white px-4 text-[13px] text-[#555] transition-colors hover:bg-[#f5f5f5]">
                导出
              </button>
            </div>
          </div>

          <div className="px-6 py-6">
            {error ? <div className="mb-4 border border-[#ffd6cc] bg-[#fff7f5] px-4 py-3 text-[13px] text-[#d63b1f]">{error}</div> : null}
            {loading ? <div className="mb-4 text-[13px] text-[#999]">订单数据加载中...</div> : null}
            <table className="w-full border-collapse text-left text-[13px]">
              {/* 表头 */}
              <thead>
                <tr className="bg-[#fafafa] text-[#999]">
                  <th className="w-[38%] py-3 pl-4 font-normal">商品</th>
                  <th className="w-[15%] py-3 font-normal text-center">规格</th>
                  <th className="w-[12%] py-3 font-normal text-center">单价</th>
                  <th className="w-[10%] py-3 font-normal text-center">数量</th>
                  <th className="w-[12%] py-3 font-normal text-center">小计</th>
                  <th className="w-[13%] py-3 pr-4 font-normal text-center">订单状态</th>
                </tr>
              </thead>

              {/* 订单列表遍历 */}
              {orders.length === 0 && !loading ? (
                <tbody>
                  <tr>
                    <td colSpan={6} className="border border-[#e5e5e5] py-12 text-center text-[#999]">暂无订单数据</td>
                  </tr>
                </tbody>
              ) : null}
              {orders.map((order, index) => (
                <tbody key={order.id}>
                  {/* 订单之间的空隙 */}
                  {index > 0 && <tr><td colSpan={6} className="h-4"></td></tr>}
                  
                  {/* 订单编号栏 */}
                  <tr className="bg-[#fafafa] border border-[#e5e5e5]">
                    <td colSpan={6} className="py-2.5 px-4 font-medium text-[#333]">
                      订单编号: {order.id}
                    </td>
                  </tr>

                  {/* 订单内的商品列表 */}
                  {order.items.map((item, itemIdx) => (
                    <tr key={item.id} className={`border-l border-r border-[#e5e5e5] ${itemIdx === order.items.length - 1 ? 'border-b' : ''}`}>
                      <td className="p-4 align-top">
                        <div className="flex items-start gap-3">
                          {item.imageUrl ? (
                            <img src={item.imageUrl} alt="" className="h-[60px] w-[60px] flex-shrink-0 border border-[#e5e5e5] object-cover" />
                          ) : (
                            <div className="flex h-[60px] w-[60px] flex-shrink-0 items-center justify-center border border-[#e5e5e5] bg-[#f6f6f6] text-[11px] text-[#999]">图</div>
                          )}
                          <div>
                            <span className={`inline-block px-1.5 py-0.5 rounded-[2px] text-[11px] leading-none font-medium mb-1.5 ${
                              item.type === 'main' ? 'bg-[#e6f7f7] text-[#00bfa5]' : 'bg-[#e6f7f7] text-[#00bfa5]'
                            }`}>
                              {item.type === 'main' ? '主商品' : '加价购商品'}
                            </span>
                            <div className="text-[13px] text-[#333] line-clamp-2 leading-tight">{item.name}</div>
                            <div className="mt-1 text-[12px] text-[#999]">SKU: {item.sku}</div>
                          </div>
                        </div>
                      </td>
                      <td className="align-middle py-4 text-center text-[#555]">{item.variation}</td>
                      <td className="align-middle py-4 text-center">
                        <div className="text-[#333]">RM {formatMoney(item.priceCurrent)}</div>
                        {item.priceOriginal && (
                          <div className="text-[#999] line-through mt-0.5 text-[12px]">RM {formatMoney(item.priceOriginal)}</div>
                        )}
                      </td>
                      <td className="align-middle py-4 text-center text-[#555]">{item.qty}</td>
                      
                      {/* 小计和状态列 (只在第一个商品渲染，并跨越所有商品行) */}
                      {itemIdx === 0 && (
                        <>
                          <td 
                            rowSpan={order.items.length} 
                            className="align-middle text-center p-4"
                          >
                            <div className="text-[#333]">RM {formatMoney(order.subtotalCurrent)}</div>
                            {order.subtotalOriginal && (
                              <div className="text-[#999] line-through mt-0.5 text-[12px]">RM {formatMoney(order.subtotalOriginal)}</div>
                            )}
                          </td>
                          <td 
                            rowSpan={order.items.length} 
                            className="align-middle text-center p-4 text-[#333]"
                          >
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
        </section>
      </div>
    </div>
  );
}
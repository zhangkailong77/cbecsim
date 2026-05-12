import { useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface VoucherOrdersViewProps {
  runId: number | null;
  voucherType: string | null;
  campaignId: number | null;
  readOnly?: boolean;
}

interface VoucherOrdersResponse {
  voucher: {
    status_label: string;
    voucher_name: string;
    reward_type_label: string;
    min_spend_text: string;
    discount_text: string;
    period: string;
    voucher_code: string;
    voucher_type_label: string;
    applicable_scope_label: string;
    display_setting_label: string;
    usage_limit: number;
    claimed_count: number;
    used_count: number;
  };
  page: number;
  page_size: number;
  total: number;
  orders: Array<{
    id: number;
    order_no: string;
    products: Array<{ image_url: string | null; product_name: string }>;
    discount_amount: number;
    total_amount: number;
    created_at_text: string;
    status_label: string;
  }>;
}

const emptyData: VoucherOrdersResponse = {
  voucher: {
    status_label: '-',
    voucher_name: '-',
    reward_type_label: '-',
    min_spend_text: '-',
    discount_text: '-',
    period: '-',
    voucher_code: '-',
    voucher_type_label: '-',
    applicable_scope_label: '-',
    display_setting_label: '-',
    usage_limit: 0,
    claimed_count: 0,
    used_count: 0,
  },
  page: 1,
  page_size: 10,
  total: 0,
  orders: [],
};

function formatAmount(value: number) {
  return Number(value || 0).toFixed(2).replace(/\.00$/, '');
}

export default function VoucherOrdersView({ runId, voucherType, campaignId, readOnly = false }: VoucherOrdersViewProps) {
  // 控制基本信息是否展开的状态
  const [isExpanded, setIsExpanded] = useState(false);
  const [page, setPage] = useState(1);
  const [jumpPage, setJumpPage] = useState('1');
  const [data, setData] = useState<VoucherOrdersResponse>(emptyData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!runId || !voucherType || !campaignId) {
      setData(emptyData);
      return;
    }
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setError('请先登录后再查看代金券订单');
      setData(emptyData);
      return;
    }

    let cancelled = false;
    const loadOrders = async () => {
      setLoading(true);
      setError('');
      try {
        const params = new URLSearchParams({ page: String(page), page_size: '10' });
        const res = await fetch(`${API_BASE_URL}/shopee/runs/${runId}/marketing/vouchers/${encodeURIComponent(voucherType)}/${campaignId}/orders?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error('load voucher orders failed');
        const payload = (await res.json()) as VoucherOrdersResponse;
        if (cancelled) return;
        setData(payload);
        setJumpPage(String(payload.page || page));
      } catch {
        if (!cancelled) {
          setError('代金券订单加载失败');
          setData(emptyData);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void loadOrders();
    return () => {
      cancelled = true;
    };
  }, [runId, voucherType, campaignId, page]);

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const visiblePages = Array.from({ length: Math.min(5, totalPages) }, (_, index) => index + 1);

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333] font-sans">
      <div className="mx-auto w-[1360px] max-w-full">
        {/* 只读模式提示 */}
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览代金券订单页，但无法创建或编辑活动。
          </div>
        )}

        {/* 基本信息模块 */}
        <div className="mb-6 rounded bg-white shadow-sm">
          <div className="px-6 pt-5 pb-8">
            <h2 className="text-lg font-medium text-[#333] mb-6">基本信息</h2>

            {/* 常驻显示区域 */}
            <div className="grid grid-cols-3 gap-y-6 gap-x-8">
              <div className="flex items-center text-sm">
                <span className="w-32 flex-shrink-0 text-[#999]">状态:</span>
                <span className="bg-[#f2f2f2] text-[#666] px-2 py-[2px] rounded text-xs border border-[#e5e5e5]">{data.voucher.status_label}</span>
              </div>
              <InfoItem label="优惠券名称" value={data.voucher.voucher_name} />
              <InfoItem label="奖励类型" value={data.voucher.reward_type_label} />

              <InfoItem label="最低消费金额" value={data.voucher.min_spend_text} />
              <InfoItem label="折扣金额" value={data.voucher.discount_text} />
              <InfoItem label="使用期限" value={data.voucher.period} />
            </div>

            {/* 折叠动画区域 */}
            <div 
              className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${
                isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
              }`}
            >
              <div className="overflow-hidden">
                <div className="grid grid-cols-3 gap-y-6 gap-x-8 pt-6">
                  <InfoItem label="优惠券代码" value={data.voucher.voucher_code} />
                  <InfoItem label="优惠券类型" value={data.voucher.voucher_type_label} />
                  <InfoItem label="适用商品" value={data.voucher.applicable_scope_label} />

                  <InfoItem label="优惠券展示设置" value={data.voucher.display_setting_label} />
                  <InfoItem label="使用数量" value={String(data.voucher.usage_limit)} tooltip />
                  <InfoItem label="已领取" value={String(data.voucher.claimed_count)} tooltip />

                  <InfoItem label="已使用" value={String(data.voucher.used_count)} tooltip />
                </div>
              </div>
            </div>

            {/* 分割线与展开/收起按钮 */}
            <div className="relative mt-8 text-center">
              <div className="absolute inset-0 flex items-center" aria-hidden="true">
                <div className="w-full border-t border-dashed border-[#e5e5e5]"></div>
              </div>
              <div className="relative flex justify-center">
                <span 
                  className="bg-white px-3 text-sm text-[#2673dd] cursor-pointer flex items-center hover:text-blue-600 transition-colors select-none"
                  onClick={() => setIsExpanded(!isExpanded)}
                >
                  {isExpanded ? '收起优惠券信息' : '更多优惠券信息'}
                  <svg 
                    className={`w-4 h-4 ml-1 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24" 
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 订单列表模块 */}
        <div className="rounded bg-white shadow-sm">
          {/* 列表头部 */}
          <div className="px-6 py-5 flex justify-between items-start">
            <div>
              <h2 className="text-lg font-medium text-[#333] mb-1">订单</h2>
              <p className="text-sm text-[#999]">{loading ? '加载中...' : error || `共 ${data.total} 个订单`}</p>
            </div>
            <div className="flex gap-3">
              <button className="px-4 py-1.5 border border-[#e5e5e5] rounded text-sm text-[#333] hover:bg-gray-50 transition-colors">
                导出
              </button>
              <button className="px-2 py-1.5 border border-[#e5e5e5] rounded text-[#666] hover:bg-gray-50 transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
              </button>
            </div>
          </div>

          {/* 表格与分页 */}
          <div className="px-6 pb-6">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#fafafa] border-y border-[#e5e5e5] text-[#999]">
                <tr>
                  <th className="py-3 px-4 font-normal w-[20%]">订单编号</th>
                  <th className="py-3 px-4 font-normal w-[20%]">商品</th>
                  <th className="py-3 px-4 font-normal w-[15%]">
                    <div className="flex items-center">
                      折扣金额
                      <QuestionTooltip />
                    </div>
                  </th>
                  <th className="py-3 px-4 font-normal w-[15%]">订单总金额</th>
                  <th className="py-3 px-4 font-normal w-[15%]">订单创建时间</th>
                  <th className="py-3 px-4 font-normal w-[15%]">订单状态</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((order) => (
                  <tr key={order.id} className="border-b border-[#e5e5e5] hover:bg-gray-50">
                    <td className="py-4 px-4 text-[#333]">{order.order_no}</td>
                    <td className="py-4 px-4">
                      <div className="flex gap-2">
                        {(order.products.length ? order.products : [{ image_url: null, product_name: 'product' }]).slice(0, 2).map((product, index) => (
                          <div key={index} className="w-10 h-10 border border-[#e5e5e5] rounded overflow-hidden bg-gray-100 flex-shrink-0">
                            {product.image_url ? (
                              <img src={product.image_url} alt={product.product_name || 'product'} className="w-full h-full object-cover" />
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </td>
                    <td className="py-4 px-4 text-[#333]">{formatAmount(order.discount_amount)}</td>
                    <td className="py-4 px-4 text-[#333]">{formatAmount(order.total_amount)}</td>
                    <td className="py-4 px-4 text-[#333]">{order.created_at_text}</td>
                    <td className="py-4 px-4 text-[#333]">{order.status_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 新增：底部翻页器组件 */}
            <div className="mt-6 flex items-center justify-end text-sm text-[#333]">
              {/* 页码区 */}
              <div className="flex items-center gap-1 mr-4">
                <button className={`flex h-8 w-8 items-center justify-center ${page <= 1 ? 'text-[#ccc] cursor-not-allowed' : 'hover:text-[#ee4d2d] transition-colors'}`} disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                </button>
                {visiblePages.map((item) => (
                  <button key={item} className={`flex h-8 min-w-[32px] items-center justify-center ${item === page ? 'text-[#ee4d2d] font-medium' : 'hover:text-[#ee4d2d] transition-colors'}`} onClick={() => setPage(item)}>{item}</button>
                ))}
                {totalPages > 6 && <span className="flex h-8 min-w-[32px] items-center justify-center text-[#999]">...</span>}
                {totalPages > 5 && <button className="flex h-8 min-w-[32px] items-center justify-center hover:text-[#ee4d2d] transition-colors" onClick={() => setPage(totalPages)}>{totalPages}</button>}
                <button className={`flex h-8 w-8 items-center justify-center ${page >= totalPages ? 'text-[#ccc] cursor-not-allowed' : 'hover:text-[#ee4d2d] transition-colors'}`} disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                </button>
              </div>

              {/* 跳转区 */}
              <div className="flex items-center gap-2">
                <span className="text-[#999]">前往</span>
                <input
                  type="text"
                  value={jumpPage}
                  onChange={(event) => setJumpPage(event.target.value)}
                  className="h-8 w-12 rounded border border-[#e5e5e5] text-center focus:border-[#ee4d2d] focus:outline-none transition-colors"
                />
                <button className="h-8 rounded border border-[#e5e5e5] px-4 hover:bg-gray-50 hover:border-[#ccc] transition-colors" onClick={() => {
                  const nextPage = Number(jumpPage);
                  if (Number.isFinite(nextPage)) setPage(Math.min(totalPages, Math.max(1, Math.floor(nextPage))));
                }}>
                  确定
                </button>
              </div>
            </div>
            {/* 分页器结束 */}

          </div>
        </div>

      </div>
    </div>
  );
}

// --- 辅助组件 ---

function InfoItem({ label, value, tooltip = false }: { label: string; value: string; tooltip?: boolean }) {
  return (
    <div className="flex text-sm">
      <span className="w-32 flex-shrink-0 text-[#999] flex items-center">
        {label}
        {tooltip && <QuestionTooltip />}
        :
      </span>
      <span className="text-[#333] pl-1 break-all">{value}</span>
    </div>
  );
}

function QuestionTooltip() {
  return (
    <svg 
      className="w-3.5 h-3.5 ml-1 text-[#bfbfbf] cursor-help" 
      fill="none" 
      stroke="currentColor" 
      viewBox="0 0 24 24" 
      xmlns="http://www.w3.org/2000/svg"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
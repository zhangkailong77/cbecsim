import { ShoppingCart, ArrowLeft } from 'lucide-react';
import shopeeLogo from '../assets/shopee-logo.svg';

type VoucherDetailType = 'shop_voucher' | 'product_voucher' | 'private_voucher' | 'live_voucher' | 'video_voucher' | 'follow_voucher';

const voucherDetailLabels: Record<VoucherDetailType, string> = {
  shop_voucher: '店铺代金券详情',
  product_voucher: '商品代金券详情',
  private_voucher: '专属代金券详情',
  live_voucher: '直播代金券详情',
  video_voucher: '视频代金券详情',
  follow_voucher: '关注礼代金券详情',
};

interface HeaderProps {
  playerName: string;
  runId: number | null;
  onBackToSetup: () => void;
  onBackToDashboard: () => void;
  onNavigateToView: (view: 'dashboard' | 'buyer-centre' | 'my-orders' | 'my-products' | 'new-product' | 'my-income' | 'my-balance' | 'bank-accounts' | 'customer-service-web' | 'customer-service-chat-management' | 'customer-service-auto-reply' | 'customer-service-quick-reply' | 'customer-service-quick-reply-create' | 'customer-service-quick-reply-edit' | 'marketing-centre' | 'marketing-discount' | 'marketing-discount-create' | 'marketing-discount-detail' | 'marketing-discount-data' | 'marketing-addon-orders' | 'marketing-bundle-orders' | 'marketing-shop-flash-sale' | 'marketing-shop-flash-sale-create' | 'marketing-shop-flash-sale-detail' | 'marketing-shop-flash-sale-data' | 'marketing-shopee-ads' | 'marketing-shipping-fee-promotion' | 'marketing-shipping-fee-promotion-create' | 'marketing-shipping-fee-promotion-update' | 'marketing-vouchers' | 'marketing-voucher-create' | 'marketing-private-voucher-create' | 'marketing-live-voucher-create' | 'marketing-video-voucher-create' | 'marketing-follow-voucher-create' | 'marketing-product-voucher-create' | 'marketing-voucher-detail' | 'marketing-voucher-orders') => void;
  activeView: 'dashboard' | 'buyer-centre' | 'my-orders' | 'my-products' | 'new-product' | 'my-income' | 'my-balance' | 'bank-accounts' | 'customer-service-web' | 'customer-service-chat-management' | 'customer-service-auto-reply' | 'customer-service-quick-reply' | 'customer-service-quick-reply-create' | 'customer-service-quick-reply-edit' | 'marketing-centre' | 'marketing-discount' | 'marketing-discount-create' | 'marketing-discount-detail' | 'marketing-discount-data' | 'marketing-addon-orders' | 'marketing-bundle-orders' | 'marketing-shop-flash-sale' | 'marketing-shop-flash-sale-create' | 'marketing-shop-flash-sale-detail' | 'marketing-shop-flash-sale-data' | 'marketing-shopee-ads' | 'marketing-shipping-fee-promotion' | 'marketing-shipping-fee-promotion-create' | 'marketing-shipping-fee-promotion-update' | 'marketing-vouchers' | 'marketing-voucher-create' | 'marketing-private-voucher-create' | 'marketing-live-voucher-create' | 'marketing-video-voucher-create' | 'marketing-follow-voucher-create' | 'marketing-product-voucher-create' | 'marketing-voucher-detail' | 'marketing-voucher-orders';
  voucherDetailType?: string;
  marketingCreateType?: 'discount' | 'bundle' | 'add_on';
  isOrderDetail?: boolean;
  isProductDetail?: boolean;
}

export default function Header({
  playerName,
  runId,
  onBackToSetup,
  onBackToDashboard,
  onNavigateToView,
  activeView,
  voucherDetailType,
  marketingCreateType = 'discount',
  isOrderDetail = false,
  isProductDetail = false,
}: HeaderProps) {
  const renderBreadcrumb = () => {
    if (activeView === 'dashboard') return null;
    if (activeView === 'customer-service-web') return null;
    if (activeView === 'customer-service-chat-management' || activeView === 'customer-service-auto-reply' || activeView === 'customer-service-quick-reply' || activeView === 'customer-service-quick-reply-create' || activeView === 'customer-service-quick-reply-edit') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('customer-service-chat-management')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            聊天管理
          </button>
          {activeView !== 'customer-service-chat-management' ? (
            <>
              <span className="text-gray-300">{'>'}</span>
              <button
                type="button"
                onClick={() => onNavigateToView(activeView === 'customer-service-auto-reply' ? 'customer-service-auto-reply' : 'customer-service-quick-reply')}
                className="text-gray-700 hover:text-[#ee4d2d]"
              >
                {activeView === 'customer-service-auto-reply' ? '自动回复' : '快捷回复'}
              </button>
              {activeView === 'customer-service-quick-reply-create' || activeView === 'customer-service-quick-reply-edit' ? (
                <>
                  <span className="text-gray-300">{'>'}</span>
                  <span className="text-gray-700">{activeView === 'customer-service-quick-reply-edit' ? '编辑快捷回复' : '新建快捷回复'}</span>
                </>
              ) : null}
            </>
          ) : null}
        </div>
      );
    }
    if (activeView === 'my-orders') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button type="button" onClick={() => onNavigateToView('my-orders')} className="text-gray-700 hover:text-[#ee4d2d]">
            我的订单
          </button>
          {isOrderDetail && (
            <>
              <span className="text-gray-300">{'>'}</span>
              <span className="text-gray-700">订单详情</span>
            </>
          )}
        </div>
      );
    }
    if (activeView === 'my-products') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button type="button" onClick={() => onNavigateToView('my-products')} className="text-gray-700 hover:text-[#ee4d2d]">
            我的产品
          </button>
        </div>
      );
    }
    if (activeView === 'my-income' || activeView === 'my-balance' || activeView === 'bank-accounts') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView(activeView)}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            {activeView === 'my-income' ? '我的收入' : activeView === 'my-balance' ? '我的余额' : '银行账户'}
          </button>
        </div>
      );
    }
    if (activeView === 'marketing-centre') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('marketing-centre')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            营销中心
          </button>
        </div>
      );
    }
    if (activeView === 'marketing-shopee-ads' || activeView === 'marketing-shipping-fee-promotion' || activeView === 'marketing-shipping-fee-promotion-create' || activeView === 'marketing-shipping-fee-promotion-update' || activeView === 'marketing-vouchers' || activeView === 'marketing-voucher-create' || activeView === 'marketing-private-voucher-create' || activeView === 'marketing-live-voucher-create' || activeView === 'marketing-video-voucher-create' || activeView === 'marketing-follow-voucher-create' || activeView === 'marketing-product-voucher-create' || activeView === 'marketing-voucher-detail' || activeView === 'marketing-voucher-orders') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('marketing-centre')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            营销中心
          </button>
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView(activeView === 'marketing-shipping-fee-promotion-create' || activeView === 'marketing-shipping-fee-promotion-update' ? 'marketing-shipping-fee-promotion' : activeView === 'marketing-voucher-create' || activeView === 'marketing-private-voucher-create' || activeView === 'marketing-live-voucher-create' || activeView === 'marketing-video-voucher-create' || activeView === 'marketing-follow-voucher-create' || activeView === 'marketing-product-voucher-create' || activeView === 'marketing-voucher-detail' || activeView === 'marketing-voucher-orders' ? 'marketing-vouchers' : activeView)}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            {activeView === 'marketing-shopee-ads' ? 'Shopee 广告' : activeView === 'marketing-shipping-fee-promotion' || activeView === 'marketing-shipping-fee-promotion-create' || activeView === 'marketing-shipping-fee-promotion-update' ? '运费促销' : '代金券'}
          </button>
          {activeView === 'marketing-shipping-fee-promotion-create' || activeView === 'marketing-shipping-fee-promotion-update' ? (
            <>
              <span className="text-gray-300">{'>'}</span>
              <span className="text-gray-700">{activeView === 'marketing-shipping-fee-promotion-update' ? '编辑运费促销' : '创建运费促销'}</span>
            </>
          ) : activeView === 'marketing-voucher-create' || activeView === 'marketing-private-voucher-create' || activeView === 'marketing-live-voucher-create' || activeView === 'marketing-video-voucher-create' || activeView === 'marketing-follow-voucher-create' || activeView === 'marketing-product-voucher-create' || activeView === 'marketing-voucher-detail' || activeView === 'marketing-voucher-orders' ? (
            <>
              <span className="text-gray-300">{'>'}</span>
              <span className="text-gray-700">
                {activeView === 'marketing-voucher-detail'
                  ? voucherDetailLabels[voucherDetailType as VoucherDetailType] || '店铺代金券详情'
                  : activeView === 'marketing-voucher-orders'
                    ? '代金券订单'
                    : activeView === 'marketing-product-voucher-create'
                    ? '创建商品代金券'
                    : activeView === 'marketing-private-voucher-create'
                      ? '创建专属代金券'
                      : activeView === 'marketing-live-voucher-create'
                        ? '创建直播代金券'
                        : activeView === 'marketing-video-voucher-create'
                          ? '创建视频代金券'
                          : activeView === 'marketing-follow-voucher-create'
                            ? '创建关注礼代金券'
                            : '创建店铺代金券'}
              </span>
            </>
          ) : null}
        </div>
      );
    }
    if (activeView === 'marketing-shop-flash-sale' || activeView === 'marketing-shop-flash-sale-create' || activeView === 'marketing-shop-flash-sale-detail' || activeView === 'marketing-shop-flash-sale-data') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('marketing-centre')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            营销中心
          </button>
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('marketing-shop-flash-sale')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            我的店铺限时抢购
          </button>
          {activeView === 'marketing-shop-flash-sale-create' || activeView === 'marketing-shop-flash-sale-detail' || activeView === 'marketing-shop-flash-sale-data' ? (
            <>
              <span className="text-gray-300">{'>'}</span>
              <span className="text-gray-700">{activeView === 'marketing-shop-flash-sale-data' ? '限时抢购数据' : activeView === 'marketing-shop-flash-sale-detail' ? '限时抢购详情' : '创建限时抢购'}</span>
            </>
          ) : null}
        </div>
      );
    }
    if (activeView === 'marketing-discount' || activeView === 'marketing-discount-create' || activeView === 'marketing-discount-detail' || activeView === 'marketing-discount-data' || activeView === 'marketing-addon-orders' || activeView === 'marketing-bundle-orders') {
      return (
        <div className="flex items-center gap-2 text-[14px]">
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('marketing-centre')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            营销中心
          </button>
          <span className="text-gray-300">{'>'}</span>
          <button
            type="button"
            onClick={() => onNavigateToView('marketing-discount')}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            折扣
          </button>
          {(activeView === 'marketing-discount-create' || activeView === 'marketing-discount-detail' || activeView === 'marketing-discount-data' || activeView === 'marketing-addon-orders' || activeView === 'marketing-bundle-orders') && (
            <>
              <span className="text-gray-300">{'>'}</span>
              <span className="text-gray-700">
                {activeView === 'marketing-addon-orders' || activeView === 'marketing-bundle-orders' ? '活动订单' : activeView === 'marketing-discount-data' ? '折扣数据' : activeView === 'marketing-discount-detail' ? '活动详情' : marketingCreateType === 'bundle' ? '创建套餐优惠' : marketingCreateType === 'add_on' ? '创建加价购' : '创建单品折扣'}
              </span>
            </>
          )}
        </div>
      );
    }
    return (
      <div className="flex items-center gap-2 text-[14px]">
        <span className="text-gray-300">{'>'}</span>
        <button type="button" onClick={() => onNavigateToView('my-products')} className="text-gray-700 hover:text-[#ee4d2d]">
          我的产品
        </button>
        <span className="text-gray-300">{'>'}</span>
        <button type="button" onClick={() => onNavigateToView('new-product')} className="text-gray-700 hover:text-[#ee4d2d]">
          {isProductDetail ? '产品详情' : '添加新商品'}
        </button>
      </div>
    );
  };

  return (
    <header className="h-[60px] bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-50">
      <div className="flex items-center gap-3">
        {activeView === 'customer-service-web' ? (
          <>
            <button type="button" onClick={onBackToDashboard} className="flex items-center">
              <img
                src={shopeeLogo}
                alt="Shopee Logo"
                className="h-8"
              />
            </button>
            <span className="text-[17px] font-bold text-[#333333]">Chat</span>
          </>
        ) : (
          <>
            <button type="button" onClick={onBackToDashboard} className="flex items-center gap-2">
              <img
                src={shopeeLogo}
                alt="Shopee Logo"
                className="h-8"
              />
              <span className="text-[17px] font-normal text-[#333333] ml-1 hover:text-[#ee4d2d]">卖家中心</span>
            </button>
            {renderBreadcrumb()}
          </>
        )}
      </div>
      
      <div className="flex items-center gap-6">
        <button
          type="button"
          onClick={() => onNavigateToView('buyer-centre')}
          className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-[12px] font-semibold text-slate-700 hover:bg-slate-50"
        >
          <ShoppingCart size={14} />
          买家中心
        </button>
        <div className="h-6 w-[1px] bg-gray-200"></div>
        <button
          type="button"
          onClick={onBackToSetup}
          className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-[12px] font-semibold text-slate-700 hover:bg-slate-50"
        >
          <ArrowLeft size={14} />
          返回工作台
        </button>

        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5">
          <svg className="text-slate-500" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21a8 8 0 0 0-16 0" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span className="text-[12px] font-semibold text-slate-700">玩家: {playerName}</span>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5">
          <span className="text-[12px] font-semibold text-slate-700">局 #{runId ?? '-'}</span>
        </div>
      </div>
    </header>
  );
}

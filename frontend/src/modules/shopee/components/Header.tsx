import { BookOpen, ArrowLeft } from 'lucide-react';
import shopeeLogo from '../assets/shopee-logo.svg';

interface HeaderProps {
  playerName: string;
  runId: number | null;
  onBackToSetup: () => void;
  onBackToDashboard: () => void;
  onNavigateToView: (view: 'dashboard' | 'my-orders' | 'my-products' | 'new-product' | 'my-income' | 'my-balance' | 'bank-accounts' | 'marketing-centre' | 'marketing-discount' | 'marketing-discount-create' | 'marketing-discount-detail' | 'marketing-discount-data' | 'marketing-addon-orders' | 'marketing-bundle-orders' | 'marketing-shop-flash-sale' | 'marketing-shop-flash-sale-create' | 'marketing-shop-flash-sale-detail' | 'marketing-shop-flash-sale-data' | 'marketing-shopee-ads' | 'marketing-vouchers') => void;
  activeView: 'dashboard' | 'my-orders' | 'my-products' | 'new-product' | 'my-income' | 'my-balance' | 'bank-accounts' | 'marketing-centre' | 'marketing-discount' | 'marketing-discount-create' | 'marketing-discount-detail' | 'marketing-discount-data' | 'marketing-addon-orders' | 'marketing-bundle-orders' | 'marketing-shop-flash-sale' | 'marketing-shop-flash-sale-create' | 'marketing-shop-flash-sale-detail' | 'marketing-shop-flash-sale-data' | 'marketing-shopee-ads' | 'marketing-vouchers';
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
  marketingCreateType = 'discount',
  isOrderDetail = false,
  isProductDetail = false,
}: HeaderProps) {
  const renderBreadcrumb = () => {
    if (activeView === 'dashboard') return null;
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
    if (activeView === 'marketing-shopee-ads' || activeView === 'marketing-vouchers') {
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
            onClick={() => onNavigateToView(activeView)}
            className="text-gray-700 hover:text-[#ee4d2d]"
          >
            {activeView === 'marketing-shopee-ads' ? 'Shopee 广告' : '代金券'}
          </button>
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
        <button type="button" onClick={onBackToDashboard} className="flex items-center gap-2">
          <img 
            src={shopeeLogo}
            alt="Shopee Logo" 
            className="h-8"
          />
          <span className="text-[17px] font-normal text-[#333333] ml-1 hover:text-[#ee4d2d]">卖家中心</span>
        </button>
        {renderBreadcrumb()}
      </div>
      
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 text-gray-500">
          <button className="hover:text-[#ee4d2d] cursor-pointer">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect width="7" height="7" x="3" y="3" rx="1" />
              <rect width="7" height="7" x="14" y="3" rx="1" />
              <rect width="7" height="7" x="14" y="14" rx="1" />
              <rect width="7" height="7" x="3" y="14" rx="1" />
            </svg>
          </button>
          <button className="hover:text-[#ee4d2d] cursor-pointer">
            <BookOpen size={20} />
          </button>
        </div>
        
        <div className="h-6 w-[1px] bg-gray-200"></div>
        
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

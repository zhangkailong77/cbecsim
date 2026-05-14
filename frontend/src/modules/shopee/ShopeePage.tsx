import { useEffect, useRef, useState } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import RightSidebar from './components/RightSidebar';
import NotificationDrawer, { type NotificationOrder } from './components/NotificationDrawer';
import ChatMessagesDrawer from './components/ChatMessagesDrawer';
import MyOrdersView from './views/MyOrdersView';
import MyOrderDetailView from './views/MyOrderDetailView';
import MyProductsView from './views/MyProductsView';
import NewProductView from './views/NewProductView';
import MyBalanceView from './views/MyBalanceView';
import MyIncomeView from './views/MyIncomeView';
import MyBankAccountsView from './views/MyBankAccountsView';
import MarketingCentreView from './views/MarketingCentreView';
import MarketingDiscountView from './views/MarketingDiscountView';
import DiscountCreateView from './views/DiscountCreateView';
import BundleCreateView from './views/BundleCreateView';
import AddOnDealCreateView from './views/AddOnDealCreateView';
import DiscountDetailView from './views/DiscountDetailView';
import DiscountDataView from './views/DiscountDataView';
import AddOnDealOrdersView from './views/AddOnDealOrdersView';
import BundleOrdersView from './views/BundleOrdersView';
import ShopFlashSaleView from './views/ShopFlashSaleView';
import ShopFlashSaleCreateView from './views/ShopFlashSaleCreateView';
import ShopFlashSaleDetailView from './views/ShopFlashSaleDetailView';
import ShopFlashSaleDataView from './views/ShopFlashSaleDataView';
import ShopeeAdsView from './views/ShopeeAdsView';
import ShippingFeePromotionView from './views/ShippingFeePromotionView';
import ShippingFeePromotionCreateView from './views/ShippingFeePromotionCreateView';
import ShopVoucherView from './views/ShopVoucherView';
import ShopVoucherCreateView from './views/ShopVoucherCreateView';
import ProductVoucherCreateView from './views/ProductVoucherCreateView';
import PrivateVoucherCreateView from './views/PrivateVoucherCreateView';
import LiveVoucherCreateView from './views/LiveVoucherCreateView';
import VideoVoucherCreateView from './views/VideoVoucherCreateView';
import FollowVoucherCreateView from './views/FollowVoucherCreateView';
import ShopVoucherDetailView from './views/ShopVoucherDetailView';
import ProductVoucherDetailView from './views/ProductVoucherDetailView';
import PrivateVoucherDetailView from './views/PrivateVoucherDetailView';
import LiveVoucherDetailView from './views/LiveVoucherDetailView';
import VideoVoucherDetailView from './views/VideoVoucherDetailView';
import FollowVoucherDetailView from './views/FollowVoucherDetailView';
import VoucherOrdersView from './views/VoucherOrdersView';
import CustomerServiceWebView from './views/CustomerServiceWebView';
import ChatManagementView from './views/ChatManagementView';
import AutoReplySettingsView from './views/AutoReplySettingsView';
import QuickReplySettingsView from './views/QuickReplySettingsView';
import QuickReplyCreateView from './views/QuickReplyCreateView';
import BuyerCentreView from './views/BuyerCentreView';
import BuyerCentreProductDetailView from './views/BuyerCentreProductDetailView';

interface ShopeePageProps {
  run: {
    id: number;
    day_index: number;
    status?: string;
  } | null;
  currentUser: {
    public_id: string;
    username: string;
    full_name: string | null;
  } | null;
  onBackToSetup: () => void;
  readOnly?: boolean;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

interface NotificationApiOrderRow {
  id: number;
  order_no: string;
  buyer_name: string;
  buyer_payment: number;
  countdown_text: string;
  created_at: string;
}

interface NotificationOrdersResponse {
  counts: {
    toship: number;
  };
  orders: NotificationApiOrderRow[];
}

const HISTORY_READONLY_DETAIL = '历史对局仅支持回溯查看，不能继续经营操作。';

type ShopeeView =
  | 'dashboard'
  | 'buyer-centre'
  | 'buyer-centre-product-detail'
  | 'my-orders'
  | 'my-products'
  | 'new-product'
  | 'my-income'
  | 'my-balance'
  | 'bank-accounts'
  | 'customer-service-web'
  | 'customer-service-chat-management'
  | 'customer-service-auto-reply'
  | 'customer-service-quick-reply'
  | 'customer-service-quick-reply-create'
  | 'customer-service-quick-reply-edit'
  | 'marketing-centre'
  | 'marketing-discount'
  | 'marketing-discount-create'
  | 'marketing-discount-detail'
  | 'marketing-discount-data'
  | 'marketing-addon-orders'
  | 'marketing-bundle-orders'
  | 'marketing-shop-flash-sale'
  | 'marketing-shop-flash-sale-create'
  | 'marketing-shop-flash-sale-detail'
  | 'marketing-shop-flash-sale-data'
  | 'marketing-shopee-ads'
  | 'marketing-shipping-fee-promotion'
  | 'marketing-shipping-fee-promotion-create'
  | 'marketing-shipping-fee-promotion-update'
  | 'marketing-vouchers'
  | 'marketing-voucher-create'
  | 'marketing-private-voucher-create'
  | 'marketing-live-voucher-create'
  | 'marketing-video-voucher-create'
  | 'marketing-follow-voucher-create'
  | 'marketing-product-voucher-create'
  | 'marketing-voucher-detail'
  | 'marketing-voucher-orders';

type MarketingCreateType = 'discount' | 'bundle' | 'add_on';

function resolveMarketingCreateType(search: string): MarketingCreateType {
  const type = new URLSearchParams(search).get('type');
  if (type === 'bundle' || type === 'add_on') return type;
  return 'discount';
}

export default function ShopeePage({ run, currentUser, onBackToSetup, readOnly = false }: ShopeePageProps) {
  const [scale, setScale] = useState(1);
  const [activeView, setActiveView] = useState<ShopeeView>(() => {
    const path = window.location.pathname;
    if (/\/shopee\/buyer-centre\/product\/?$/.test(path)) return 'buyer-centre-product-detail';
    if (/\/shopee\/buyer-centre\/?$/.test(path)) return 'buyer-centre';
    if (/\/shopee\/order(?:\/\d+)?\/?$/.test(path)) return 'my-orders';
    if (/\/shopee\/product\/add_news\/?$/.test(path)) return 'new-product';
    if (/\/shopee\/product\/list\/(all|live|violation|review|unpublished)\/?$/.test(path)) return 'my-products';
    if (/\/shopee\/customer-service\/web\/?$/.test(path)) return 'customer-service-web';
    if (/\/shopee\/customer-service\/chat-management\/auto-reply\/?$/.test(path)) return 'customer-service-auto-reply';
    if (/\/shopee\/customer-service\/chat-management\/quick-reply\/edit\/?$/.test(path)) return 'customer-service-quick-reply-edit';
    if (/\/shopee\/customer-service\/chat-management\/quick-reply\/create\/?$/.test(path)) return 'customer-service-quick-reply-create';
    if (/\/shopee\/customer-service\/chat-management\/quick-reply\/?$/.test(path)) return 'customer-service-quick-reply';
    if (/\/shopee\/customer-service\/chat-management\/?$/.test(path)) return 'customer-service-chat-management';
    if (/\/shopee\/marketing-centre\/?$/.test(path)) return 'marketing-centre';
    if (/\/shopee\/marketing\/discount\/create\/?$/.test(path)) return 'marketing-discount-create';
    if (/\/shopee\/marketing\/discount\/detail\/?$/.test(path)) return 'marketing-discount-detail';
    if (/\/shopee\/marketing\/discount\/data\/?$/.test(path)) return 'marketing-discount-data';
    if (/\/shopee\/marketing\/add-on\/orders\/?$/.test(path)) return 'marketing-addon-orders';
    if (/\/shopee\/marketing\/bundle\/orders\/?$/.test(path)) return 'marketing-bundle-orders';
    if (/\/shopee\/marketing\/flash-sale\/create\/?$/.test(path)) return 'marketing-shop-flash-sale-create';
    if (/\/shopee\/marketing\/flash-sale\/detail\/?$/.test(path)) return 'marketing-shop-flash-sale-detail';
    if (/\/shopee\/marketing\/flash-sale\/data\/?$/.test(path)) return 'marketing-shop-flash-sale-data';
    if (/\/shopee\/marketing\/flash-sale\/?$/.test(path)) return 'marketing-shop-flash-sale';
    if (/\/shopee\/marketing\/shopee-ads\/?$/.test(path)) return 'marketing-shopee-ads';
    if (/\/shopee\/marketing\/shipping-fee-promotion\/create\/?$/.test(path)) return 'marketing-shipping-fee-promotion-create';
    if (/\/shopee\/marketing\/shipping-fee-promotion\/update\/?$/.test(path)) return 'marketing-shipping-fee-promotion-update';
    if (/\/shopee\/marketing\/shipping-fee-promotion\/?$/.test(path)) return 'marketing-shipping-fee-promotion';
    if (/\/shopee\/marketing\/vouchers\/orders\/?$/.test(path)) return 'marketing-voucher-orders';
    if (/\/shopee\/marketing\/vouchers\/detail\/?$/.test(path)) return 'marketing-voucher-detail';
    if (/\/shopee\/marketing\/vouchers\/product-create\/?$/.test(path)) return 'marketing-product-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/private-create\/?$/.test(path)) return 'marketing-private-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/live-create\/?$/.test(path)) return 'marketing-live-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/video-create\/?$/.test(path)) return 'marketing-video-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/follow-create\/?$/.test(path)) return 'marketing-follow-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/create\/?$/.test(path)) return 'marketing-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/?$/.test(path)) return 'marketing-vouchers';
    if (/\/shopee\/marketing\/discount\/?$/.test(path)) return 'marketing-discount';
    if (/\/shopee\/finance\/income\/?$/.test(path)) return 'my-income';
    if (/\/shopee\/finance\/balance\/?$/.test(path)) return 'my-balance';
    if (/\/shopee\/finance\/bank-accounts\/?$/.test(path)) return 'bank-accounts';
    return 'dashboard';
  });
  const [editingListingId, setEditingListingId] = useState<number | null>(() => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('listing_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const [buyerCentreListingId, setBuyerCentreListingId] = useState<number | null>(() => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('listing_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const [activeOrderId, setActiveOrderId] = useState<number | null>(() => {
    const matched = window.location.pathname.match(/\/shopee\/order\/(\d+)\/?$/);
    if (!matched) return null;
    const val = Number(matched[1]);
    return Number.isFinite(val) && val > 0 ? val : null;
  });
  const [orderReturnType, setOrderReturnType] = useState<string>(() => {
    const search = new URLSearchParams(window.location.search);
    return search.get('type') || 'all';
  });
  const [marketingCreateType, setMarketingCreateType] = useState<MarketingCreateType>(() => resolveMarketingCreateType(window.location.search));
  const [activeDiscountCampaignId, setActiveDiscountCampaignId] = useState<number | null>(() => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('campaign_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const [activeFlashSaleCampaignId, setActiveFlashSaleCampaignId] = useState<number | null>(() => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('campaign_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const [activeShippingFeePromotionId, setActiveShippingFeePromotionId] = useState<number | null>(() => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('id') || search.get('campaign_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const [editingQuickReplyGroupId, setEditingQuickReplyGroupId] = useState<number | null>(() => {
    const raw = Number(new URLSearchParams(window.location.search).get('group_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  });
  const [editingQuickReplyGroup, setEditingQuickReplyGroup] = useState<{
    id: number;
    group_name: string;
    enabled: boolean;
    sort_order: number;
    message_count: number;
    messages: { id: number; message: string; tags: string[]; sort_order: number }[];
  } | null>(null);
  const [activeVoucherCampaign, setActiveVoucherCampaign] = useState<{ voucherType: string; campaignId: number } | null>(() => {
    const search = new URLSearchParams(window.location.search);
    const campaignId = Number(search.get('campaign_id') || '');
    const voucherType = search.get('voucher_type') || '';
    return voucherType && Number.isFinite(campaignId) && campaignId > 0 ? { voucherType, campaignId } : null;
  });
  const [notificationDrawerOpen, setNotificationDrawerOpen] = useState(false);
  const [chatMessagesDrawerOpen, setChatMessagesDrawerOpen] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);
  const [chatUnreadCount, setChatUnreadCount] = useState(0);
  const [notificationOrders, setNotificationOrders] = useState<NotificationOrder[]>([]);
  const [notificationLoading, setNotificationLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const BASE_WIDTH = 1920;
  const BASE_HEIGHT = 1080;

  const parseShopeeViewFromPath = () => {
    const path = window.location.pathname;
    if (/\/shopee\/buyer-centre\/product\/?$/.test(path)) return 'buyer-centre-product-detail';
    if (/\/shopee\/buyer-centre\/?$/.test(path)) return 'buyer-centre';
    if (/\/shopee\/order(?:\/\d+)?\/?$/.test(path)) return 'my-orders';
    if (/\/shopee\/product\/add_news\/?$/.test(path)) return 'new-product';
    if (/\/shopee\/product\/list\/(all|live|violation|review|unpublished)\/?$/.test(path)) return 'my-products';
    if (/\/shopee\/customer-service\/web\/?$/.test(path)) return 'customer-service-web';
    if (/\/shopee\/customer-service\/chat-management\/auto-reply\/?$/.test(path)) return 'customer-service-auto-reply';
    if (/\/shopee\/customer-service\/chat-management\/quick-reply\/edit\/?$/.test(path)) return 'customer-service-quick-reply-edit';
    if (/\/shopee\/customer-service\/chat-management\/quick-reply\/create\/?$/.test(path)) return 'customer-service-quick-reply-create';
    if (/\/shopee\/customer-service\/chat-management\/quick-reply\/?$/.test(path)) return 'customer-service-quick-reply';
    if (/\/shopee\/customer-service\/chat-management\/?$/.test(path)) return 'customer-service-chat-management';
    if (/\/shopee\/marketing-centre\/?$/.test(path)) return 'marketing-centre';
    if (/\/shopee\/marketing\/discount\/create\/?$/.test(path)) return 'marketing-discount-create';
    if (/\/shopee\/marketing\/discount\/detail\/?$/.test(path)) return 'marketing-discount-detail';
    if (/\/shopee\/marketing\/discount\/data\/?$/.test(path)) return 'marketing-discount-data';
    if (/\/shopee\/marketing\/add-on\/orders\/?$/.test(path)) return 'marketing-addon-orders';
    if (/\/shopee\/marketing\/bundle\/orders\/?$/.test(path)) return 'marketing-bundle-orders';
    if (/\/shopee\/marketing\/flash-sale\/create\/?$/.test(path)) return 'marketing-shop-flash-sale-create';
    if (/\/shopee\/marketing\/flash-sale\/detail\/?$/.test(path)) return 'marketing-shop-flash-sale-detail';
    if (/\/shopee\/marketing\/flash-sale\/data\/?$/.test(path)) return 'marketing-shop-flash-sale-data';
    if (/\/shopee\/marketing\/flash-sale\/?$/.test(path)) return 'marketing-shop-flash-sale';
    if (/\/shopee\/marketing\/shopee-ads\/?$/.test(path)) return 'marketing-shopee-ads';
    if (/\/shopee\/marketing\/shipping-fee-promotion\/create\/?$/.test(path)) return 'marketing-shipping-fee-promotion-create';
    if (/\/shopee\/marketing\/shipping-fee-promotion\/update\/?$/.test(path)) return 'marketing-shipping-fee-promotion-update';
    if (/\/shopee\/marketing\/shipping-fee-promotion\/?$/.test(path)) return 'marketing-shipping-fee-promotion';
    if (/\/shopee\/marketing\/vouchers\/orders\/?$/.test(path)) return 'marketing-voucher-orders';
    if (/\/shopee\/marketing\/vouchers\/detail\/?$/.test(path)) return 'marketing-voucher-detail';
    if (/\/shopee\/marketing\/vouchers\/product-create\/?$/.test(path)) return 'marketing-product-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/private-create\/?$/.test(path)) return 'marketing-private-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/live-create\/?$/.test(path)) return 'marketing-live-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/video-create\/?$/.test(path)) return 'marketing-video-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/follow-create\/?$/.test(path)) return 'marketing-follow-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/create\/?$/.test(path)) return 'marketing-voucher-create';
    if (/\/shopee\/marketing\/vouchers\/?$/.test(path)) return 'marketing-vouchers';
    if (/\/shopee\/marketing\/discount\/?$/.test(path)) return 'marketing-discount';
    if (/\/shopee\/finance\/income\/?$/.test(path)) return 'my-income';
    if (/\/shopee\/finance\/balance\/?$/.test(path)) return 'my-balance';
    if (/\/shopee\/finance\/bank-accounts\/?$/.test(path)) return 'bank-accounts';
    return 'dashboard';
  };

  const withHistoryRunId = (path: string) => {
    if (!readOnly || !run?.id) return path;
    const [pathname, query = ''] = path.split('?');
    const params = new URLSearchParams(query);
    params.set('run_id', String(run.id));
    const nextQuery = params.toString();
    return nextQuery ? `${pathname}?${nextQuery}` : pathname;
  };

  const buildShopeePath = (view: ShopeeView) => {
    const base = `/u/${encodeURIComponent(currentUser?.public_id ?? '')}/shopee`;
    if (view === 'buyer-centre') return `${base}/buyer-centre`;
    if (view === 'buyer-centre-product-detail') return `${base}/buyer-centre/product`;
    if (view === 'new-product') return `${base}/product/add_news`;
    if (view === 'marketing-centre') return `${base}/marketing-centre`;
    if (view === 'marketing-discount') return `${base}/marketing/discount`;
    if (view === 'marketing-discount-create') return `${base}/marketing/discount/create?type=discount`;
    if (view === 'marketing-discount-detail') return `${base}/marketing/discount/detail`;
    if (view === 'marketing-discount-data') return `${base}/marketing/discount/data`;
    if (view === 'marketing-addon-orders') return `${base}/marketing/add-on/orders`;
    if (view === 'marketing-bundle-orders') return `${base}/marketing/bundle/orders`;
    if (view === 'marketing-shop-flash-sale') return `${base}/marketing/flash-sale`;
    if (view === 'marketing-shop-flash-sale-create') return `${base}/marketing/flash-sale/create`;
    if (view === 'marketing-shop-flash-sale-detail') return `${base}/marketing/flash-sale/detail`;
    if (view === 'marketing-shop-flash-sale-data') return `${base}/marketing/flash-sale/data`;
    if (view === 'marketing-shopee-ads') return `${base}/marketing/shopee-ads`;
    if (view === 'marketing-shipping-fee-promotion') return `${base}/marketing/shipping-fee-promotion`;
    if (view === 'marketing-shipping-fee-promotion-create') return `${base}/marketing/shipping-fee-promotion/create`;
    if (view === 'marketing-shipping-fee-promotion-update') return `${base}/marketing/shipping-fee-promotion/update`;
    if (view === 'marketing-voucher-create') return `${base}/marketing/vouchers/create`;
    if (view === 'marketing-private-voucher-create') return `${base}/marketing/vouchers/private-create`;
    if (view === 'marketing-live-voucher-create') return `${base}/marketing/vouchers/live-create`;
    if (view === 'marketing-video-voucher-create') return `${base}/marketing/vouchers/video-create`;
    if (view === 'marketing-follow-voucher-create') return `${base}/marketing/vouchers/follow-create`;
    if (view === 'marketing-product-voucher-create') return `${base}/marketing/vouchers/product-create`;
    if (view === 'marketing-voucher-detail') return `${base}/marketing/vouchers/detail`;
    if (view === 'marketing-voucher-orders') return `${base}/marketing/vouchers/orders`;
    if (view === 'marketing-vouchers') return `${base}/marketing/vouchers`;
    if (view === 'my-income') return `${base}/finance/income`;
    if (view === 'my-balance') return `${base}/finance/balance`;
    if (view === 'bank-accounts') return `${base}/finance/bank-accounts`;
    if (view === 'customer-service-web') return `${base}/customer-service/web`;
    if (view === 'customer-service-auto-reply') return `${base}/customer-service/chat-management/auto-reply`;
    if (view === 'customer-service-quick-reply-create') return `${base}/customer-service/chat-management/quick-reply/create`;
    if (view === 'customer-service-quick-reply-edit') return `${base}/customer-service/chat-management/quick-reply/edit`;
    if (view === 'customer-service-quick-reply') return `${base}/customer-service/chat-management/quick-reply`;
    if (view === 'customer-service-chat-management') return `${base}/customer-service/chat-management`;
    return view === 'my-orders' ? `${base}/order` : base;
  };

  const parseOrderIdFromPath = () => {
    const matched = window.location.pathname.match(/\/shopee\/order\/(\d+)\/?$/);
    if (!matched) return null;
    const val = Number(matched[1]);
    return Number.isFinite(val) && val > 0 ? val : null;
  };

  const parseEditingListingIdFromPath = () => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('listing_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  };

  const parseBuyerCentreListingIdFromPath = () => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('listing_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  };

  const parseDiscountCampaignIdFromPath = () => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('campaign_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  };

  const parseFlashSaleCampaignIdFromPath = () => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('campaign_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  };

  const parseShippingFeePromotionIdFromPath = () => {
    const search = new URLSearchParams(window.location.search);
    const raw = Number(search.get('id') || search.get('campaign_id') || '');
    return Number.isFinite(raw) && raw > 0 ? raw : null;
  };

  const parseVoucherCampaignFromPath = (): { voucherType: string; campaignId: number } | null => {
    const search = new URLSearchParams(window.location.search);
    const campaignId = Number(search.get('campaign_id') || '');
    const voucherType = search.get('voucher_type') || '';
    return voucherType && Number.isFinite(campaignId) && campaignId > 0 ? { voucherType, campaignId } : null;
  };

  useEffect(() => {
    const onPopState = () => {
      setActiveView(parseShopeeViewFromPath());
      setEditingListingId(parseEditingListingIdFromPath());
      setBuyerCentreListingId(parseBuyerCentreListingIdFromPath());
      setActiveOrderId(parseOrderIdFromPath());
      setActiveDiscountCampaignId(parseDiscountCampaignIdFromPath());
      setActiveFlashSaleCampaignId(parseFlashSaleCampaignIdFromPath());
      setActiveShippingFeePromotionId(parseShippingFeePromotionIdFromPath());
      setActiveVoucherCampaign(parseVoucherCampaignFromPath());
      setOrderReturnType(new URLSearchParams(window.location.search).get('type') || 'all');
      setMarketingCreateType(resolveMarketingCreateType(window.location.search));
      const quickReplyGroupId = Number(new URLSearchParams(window.location.search).get('group_id') || '');
      setEditingQuickReplyGroupId(Number.isFinite(quickReplyGroupId) && quickReplyGroupId > 0 ? quickReplyGroupId : null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    if (!readOnly) return;
    const allowed = new Set(['dashboard', 'buyer-centre', 'buyer-centre-product-detail', 'my-orders', 'my-products', 'new-product', 'my-income', 'my-balance', 'bank-accounts', 'marketing-centre', 'marketing-discount', 'marketing-discount-create', 'marketing-discount-detail', 'marketing-discount-data', 'marketing-addon-orders', 'marketing-bundle-orders', 'marketing-shop-flash-sale', 'marketing-shop-flash-sale-create', 'marketing-shop-flash-sale-detail', 'marketing-shop-flash-sale-data', 'marketing-shopee-ads', 'marketing-shipping-fee-promotion', 'marketing-shipping-fee-promotion-create', 'marketing-shipping-fee-promotion-update', 'marketing-vouchers', 'marketing-voucher-create', 'marketing-product-voucher-create', 'marketing-private-voucher-create']);
    if (!allowed.has(activeView)) {
      setActiveView('my-orders');
      const nextPath = withHistoryRunId(buildShopeePath('my-orders'));
      if (`${window.location.pathname}${window.location.search}` !== nextPath) {
        window.history.replaceState(null, '', nextPath);
      }
    }
  }, [activeView, readOnly]);

  useEffect(() => {
    if (!run?.id) {
      setNotificationCount(0);
      setChatUnreadCount(0);
      setNotificationOrders([]);
      return;
    }

    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setNotificationCount(0);
      setChatUnreadCount(0);
      setNotificationOrders([]);
      return;
    }

    let cancelled = false;
    const loadNotifications = async () => {
      setNotificationLoading(true);
      try {
        const params = new URLSearchParams({
          type: 'toship',
          source: 'to_process',
          sort_by: 'ship_by_date_asc',
          page: '1',
          page_size: '20',
        });
        const res = await fetch(`${API_BASE_URL}/shopee/runs/${run.id}/orders?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error('load notification failed');
        const data = (await res.json()) as NotificationOrdersResponse;
        if (cancelled) return;
        const mapped = (data.orders ?? []).map((item) => ({
          id: item.id,
          orderNo: item.order_no,
          buyerName: item.buyer_name || '买家',
          amountText: `RM${Number(item.buyer_payment || 0).toFixed(2)}`,
          countdownText: item.countdown_text || '请尽快处理',
          createdAtText: new Date(item.created_at).toLocaleString(),
        }));
        setNotificationCount(Math.max(0, Number(data.counts?.toship ?? 0)));
        setNotificationOrders(mapped);

        const chatRes = await fetch(`${API_BASE_URL}/shopee/runs/${run.id}/customer-service/conversations?status=open&page=1&page_size=50`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!chatRes.ok) throw new Error('load chat messages failed');
        const chatData = await chatRes.json();
        if (cancelled) return;
        const unreadTotal = (chatData.items ?? []).reduce((sum: number, item: any) => sum + Number(item.unread_count ?? 0), 0);
        setChatUnreadCount(Math.max(0, unreadTotal));
      } catch {
        if (!cancelled) {
          setNotificationCount(0);
          setChatUnreadCount(0);
          setNotificationOrders([]);
        }
      } finally {
        if (!cancelled) setNotificationLoading(false);
      }
    };

    void loadNotifications();
    const timer = window.setInterval(() => {
      void loadNotifications();
    }, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [run?.id, activeView]);

  const handleSelectView = (view: ShopeeView, listingId?: number | null) => {
    if (readOnly) {
      const allowed = new Set(['dashboard', 'buyer-centre', 'buyer-centre-product-detail', 'my-orders', 'my-products', 'new-product', 'my-income', 'my-balance', 'bank-accounts', 'marketing-centre', 'marketing-discount', 'marketing-discount-create', 'marketing-discount-detail', 'marketing-discount-data', 'marketing-addon-orders', 'marketing-bundle-orders', 'marketing-shop-flash-sale', 'marketing-shop-flash-sale-create', 'marketing-shop-flash-sale-detail', 'marketing-shop-flash-sale-data', 'marketing-shopee-ads', 'marketing-shipping-fee-promotion', 'marketing-shipping-fee-promotion-create', 'marketing-shipping-fee-promotion-update', 'marketing-vouchers', 'marketing-voucher-create', 'marketing-product-voucher-create', 'marketing-private-voucher-create']);
      if (!allowed.has(view)) {
        alert(HISTORY_READONLY_DETAIL);
        return;
      }
    }
    if (!currentUser?.public_id) {
      setActiveView(view);
      return;
    }
    let nextPath = '';
    if (view === 'my-orders') {
      const base = buildShopeePath('my-orders');
      const query = orderReturnType && orderReturnType !== 'all' ? `?type=${encodeURIComponent(orderReturnType)}` : '';
      nextPath = `${base}${query}`;
    } else {
      const nextPathBase = view === 'my-products' ? `${buildShopeePath('dashboard')}/product/list/all` : buildShopeePath(view);
      nextPath = view === 'buyer-centre-product-detail' && listingId && listingId > 0
        ? `${nextPathBase}?listing_id=${listingId}`
        : view === 'new-product' && listingId && listingId > 0
          ? `${nextPathBase}?listing_id=${listingId}`
          : view === 'customer-service-quick-reply-edit' && listingId && listingId > 0
          ? `${nextPathBase}?group_id=${listingId}`
          : view === 'marketing-shipping-fee-promotion-update' && listingId && listingId > 0
            ? `${nextPathBase}?id=${listingId}`
            : nextPathBase;
    }
    const nextPathWithRunId = withHistoryRunId(nextPath);
    const currentFullPath = `${window.location.pathname}${window.location.search}`;
    if (currentFullPath !== nextPathWithRunId) {
      window.history.pushState(null, '', nextPathWithRunId);
    }
    setEditingListingId(view === 'new-product' ? (listingId && listingId > 0 ? listingId : null) : null);
    setBuyerCentreListingId(view === 'buyer-centre-product-detail' ? (listingId && listingId > 0 ? listingId : null) : null);
    setEditingQuickReplyGroupId(view === 'customer-service-quick-reply-edit' ? (listingId && listingId > 0 ? listingId : null) : null);
    setActiveOrderId(null);
    setActiveDiscountCampaignId(null);
    setActiveFlashSaleCampaignId(null);
    setActiveShippingFeePromotionId(view === 'marketing-shipping-fee-promotion-update' ? (listingId && listingId > 0 ? listingId : null) : null);
    setActiveView(view);
    if (view === 'marketing-discount-create') {
      setMarketingCreateType(resolveMarketingCreateType(nextPathWithRunId.includes('?') ? `?${nextPathWithRunId.split('?')[1]}` : ''));
    }
  };

  const handleEditQuickReplyGroup = (group: NonNullable<typeof editingQuickReplyGroup>) => {
    setEditingQuickReplyGroup(group);
    handleSelectView('customer-service-quick-reply-edit', group.id);
  };

  const handleBackToQuickReply = () => {
    setEditingQuickReplyGroup(null);
    setEditingQuickReplyGroupId(null);
    handleSelectView('customer-service-quick-reply');
  };

  const handleOpenVoucherDetail = (voucherType: string, campaignId: number) => {
    if (!currentUser?.public_id) return;
    const path = withHistoryRunId(
      `/u/${encodeURIComponent(currentUser.public_id)}/shopee/marketing/vouchers/detail?voucher_type=${encodeURIComponent(voucherType)}&campaign_id=${campaignId}`
    );
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState(null, '', path);
    }
    setActiveOrderId(null);
    setActiveDiscountCampaignId(null);
    setActiveFlashSaleCampaignId(null);
    setActiveVoucherCampaign({ voucherType, campaignId });
    setActiveView('marketing-voucher-detail');
  };

  const handleOpenVoucherOrders = (voucherType: string, campaignId: number) => {
    if (!currentUser?.public_id) return;
    const path = withHistoryRunId(
      `/u/${encodeURIComponent(currentUser.public_id)}/shopee/marketing/vouchers/orders?voucher_type=${encodeURIComponent(voucherType)}&campaign_id=${campaignId}`
    );
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState(null, '', path);
    }
    setActiveOrderId(null);
    setActiveDiscountCampaignId(null);
    setActiveFlashSaleCampaignId(null);
    setActiveVoucherCampaign({ voucherType, campaignId });
    setActiveView('marketing-voucher-orders');
  };

  const handleOpenFlashSaleDetail = (campaignId: number) => {
    if (!currentUser?.public_id) return;
    const path = withHistoryRunId(
      `/u/${encodeURIComponent(currentUser.public_id)}/shopee/marketing/flash-sale/detail?campaign_id=${campaignId}`
    );
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState(null, '', path);
    }
    setActiveOrderId(null);
    setActiveDiscountCampaignId(null);
    setActiveFlashSaleCampaignId(campaignId);
    setActiveView('marketing-shop-flash-sale-detail');
  };

  const handleOpenFlashSaleData = (campaignId: number) => {
    if (!currentUser?.public_id) return;
    const path = withHistoryRunId(
      `/u/${encodeURIComponent(currentUser.public_id)}/shopee/marketing/flash-sale/data?campaign_id=${campaignId}`
    );
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState(null, '', path);
    }
    setActiveOrderId(null);
    setActiveDiscountCampaignId(null);
    setActiveFlashSaleCampaignId(campaignId);
    setActiveView('marketing-shop-flash-sale-data');
  };

  const handleOpenOrderDetail = (orderId: number, tabType: string) => {
    if (!currentUser?.public_id) return;
    const path = withHistoryRunId(
      `/u/${encodeURIComponent(currentUser.public_id)}/shopee/order/${orderId}?type=${encodeURIComponent(tabType || 'all')}`
    );
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState(null, '', path);
    }
    setActiveView('my-orders');
    setActiveOrderId(orderId);
    setActiveDiscountCampaignId(null);
    setOrderReturnType(tabType || 'all');
  };

  const handleBackToOrderList = () => {
    if (!currentUser?.public_id) return;
    const base = `/u/${encodeURIComponent(currentUser.public_id)}/shopee/order`;
    const query = orderReturnType && orderReturnType !== 'all' ? `?type=${encodeURIComponent(orderReturnType)}` : '';
    const path = withHistoryRunId(`${base}${query}`);
    if (`${window.location.pathname}${window.location.search}` !== path) {
      window.history.pushState(null, '', path);
    }
    setActiveOrderId(null);
    setActiveDiscountCampaignId(null);
    setActiveView('my-orders');
  };

  useEffect(() => {
    const handleResize = () => {
      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = document.documentElement.clientHeight;
      const widthScale = viewportWidth / BASE_WIDTH;
      const heightScale = viewportHeight / BASE_HEIGHT;
      setScale(Math.max(widthScale, heightScale));
    };

    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const playerDisplayName = currentUser?.full_name?.trim() || currentUser?.username || '玩家';

  if (activeView === 'buyer-centre') {
    return (
      <BuyerCentreView
        runId={run?.id ?? null}
        readOnly={readOnly}
        onOpenProductDetail={(listingId) => handleSelectView('buyer-centre-product-detail', listingId)}
        onBackToSellerCentre={() => handleSelectView('dashboard')}
      />
    );
  }

  if (activeView === 'buyer-centre-product-detail') {
    return (
      <BuyerCentreProductDetailView
        listingId={buyerCentreListingId}
        onBackToBuyerCentre={() => handleSelectView('buyer-centre')}
        onBackToSellerCentre={() => handleSelectView('dashboard')}
      />
    );
  }

  return (
    <div className="fixed inset-0 overflow-auto bg-white">
      <div
        ref={containerRef}
        className="bg-white shadow-2xl flex flex-col flex-shrink-0"
        style={{
          width: `${BASE_WIDTH}px`,
          height: `${BASE_HEIGHT}px`,
          transform: `scale(${scale})`,
          transformOrigin: 'top left',
          transition: 'transform 0.1s ease-out',
          position: 'absolute',
          left: 0,
          top: 0,
          fontFamily:
            '"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Helvetica Neue",Arial,sans-serif',
          fontSize: '14px',
        }}
      >
        <Header
          playerName={playerDisplayName}
          runId={run?.id ?? null}
          onBackToSetup={onBackToSetup}
          onBackToDashboard={() => handleSelectView('dashboard')}
          onNavigateToView={handleSelectView}
          activeView={activeView}
          voucherDetailType={activeVoucherCampaign?.voucherType}
          marketingCreateType={marketingCreateType}
          isOrderDetail={Boolean(activeOrderId)}
          isProductDetail={activeView === 'new-product' && Boolean(editingListingId)}
        />
        <div className="flex flex-1 overflow-hidden">
          {readOnly && (
            <div className="absolute left-[220px] top-[68px] z-20 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-[12px] text-amber-700">
              历史对局回溯模式：按钮保留，写操作将提示只读。
            </div>
          )}
          <div className="flex min-w-0 flex-1 overflow-hidden">
            {activeView !== 'new-product' && activeView !== 'customer-service-web' && activeView !== 'customer-service-auto-reply' && activeView !== 'customer-service-quick-reply' && activeView !== 'customer-service-quick-reply-create' && activeView !== 'customer-service-quick-reply-edit' && activeView !== 'marketing-discount-create' && activeView !== 'marketing-discount-detail' && activeView !== 'marketing-discount-data' && activeView !== 'marketing-addon-orders' && activeView !== 'marketing-bundle-orders' && activeView !== 'marketing-shop-flash-sale-create' && activeView !== 'marketing-shop-flash-sale-detail' && activeView !== 'marketing-shop-flash-sale-data' && activeView !== 'marketing-shipping-fee-promotion-create' && activeView !== 'marketing-shipping-fee-promotion-update' && activeView !== 'marketing-voucher-create' && activeView !== 'marketing-private-voucher-create' && activeView !== 'marketing-live-voucher-create' && activeView !== 'marketing-video-voucher-create' && activeView !== 'marketing-follow-voucher-create' && activeView !== 'marketing-product-voucher-create' && activeView !== 'marketing-voucher-detail' && activeView !== 'marketing-voucher-orders' && !activeOrderId && (
              <Sidebar activeView={activeView} onSelectView={handleSelectView} />
            )}
            {activeView === 'my-orders' ? (
              activeOrderId ? (
                <MyOrderDetailView
                  runId={run?.id ?? null}
                  orderId={activeOrderId}
                  onBack={handleBackToOrderList}
                  readOnly={readOnly}
                />
              ) : (
                <MyOrdersView runId={run?.id ?? null} onOpenOrderDetail={handleOpenOrderDetail} readOnly={readOnly} />
              )
            ) : activeView === 'my-products' ? (
              <MyProductsView
                runId={run?.id ?? null}
                readOnly={readOnly}
                onGotoNewProduct={(listingId) => handleSelectView('new-product', listingId)}
              />
            ) : activeView === 'new-product' ? (
              <NewProductView
                runId={run?.id ?? null}
                editingListingId={editingListingId}
                onBackToProducts={() => handleSelectView('my-products')}
                readOnly={readOnly}
              />
            ) : activeView === 'my-balance' ? (
              <MyBalanceView runId={run?.id ?? null} onOpenBankAccounts={() => handleSelectView('bank-accounts')} readOnly={readOnly} />
            ) : activeView === 'my-income' ? (
              <MyIncomeView runId={run?.id ?? null} />
            ) : activeView === 'bank-accounts' ? (
              <MyBankAccountsView runId={run?.id ?? null} readOnly={readOnly} />
            ) : activeView === 'customer-service-web' ? (
              <CustomerServiceWebView runId={run?.id ?? null} readOnly={readOnly} />
            ) : activeView === 'customer-service-chat-management' ? (
              <ChatManagementView
                onOpenAutoReply={() => handleSelectView('customer-service-auto-reply')}
                onOpenQuickReply={() => handleSelectView('customer-service-quick-reply')}
              />
            ) : activeView === 'customer-service-auto-reply' ? (
              <AutoReplySettingsView runId={run?.id ?? null} readOnly={readOnly} />
            ) : activeView === 'customer-service-quick-reply' ? (
              <QuickReplySettingsView
                runId={run?.id ?? null}
                readOnly={readOnly}
                onCreateQuickReply={() => handleSelectView('customer-service-quick-reply-create')}
                onEditQuickReply={handleEditQuickReplyGroup}
              />
            ) : activeView === 'customer-service-quick-reply-create' ? (
              <QuickReplyCreateView
                runId={run?.id ?? null}
                readOnly={readOnly}
                onBackToQuickReply={handleBackToQuickReply}
              />
            ) : activeView === 'customer-service-quick-reply-edit' ? (
              <QuickReplyCreateView
                runId={run?.id ?? null}
                readOnly={readOnly}
                editingGroup={editingQuickReplyGroup?.id === editingQuickReplyGroupId ? editingQuickReplyGroup : null}
                onBackToQuickReply={handleBackToQuickReply}
              />
            ) : activeView === 'marketing-discount-create' ? (
              marketingCreateType === 'bundle' ? (
                <BundleCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToDiscount={() => handleSelectView('marketing-discount')} />
              ) : marketingCreateType === 'add_on' ? (
                <AddOnDealCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToDiscount={() => handleSelectView('marketing-discount')} />
              ) : (
                <DiscountCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToDiscount={() => handleSelectView('marketing-discount')} />
              )
            ) : activeView === 'marketing-discount-detail' ? (
              <DiscountDetailView
                runId={run?.id ?? null}
                campaignId={activeDiscountCampaignId}
                readOnly={readOnly}
                onBackToDiscount={() => handleSelectView('marketing-discount')}
                onOpenOrderDetail={handleOpenOrderDetail}
              />
            ) : activeView === 'marketing-discount-data' ? (
              <DiscountDataView
                runId={run?.id ?? null}
                campaignId={activeDiscountCampaignId}
                publicId={currentUser?.public_id ?? ''}
                readOnly={readOnly}
                onBackToDiscount={() => handleSelectView('marketing-discount')}
              />
            ) : activeView === 'marketing-addon-orders' ? (
              <AddOnDealOrdersView
                runId={run?.id ?? null}
                campaignId={activeDiscountCampaignId}
                onBackToDiscount={() => handleSelectView('marketing-discount')}
              />
            ) : activeView === 'marketing-bundle-orders' ? (
              <BundleOrdersView
                runId={run?.id ?? null}
                campaignId={activeDiscountCampaignId}
              />
            ) : activeView === 'marketing-shop-flash-sale-create' ? (
              <ShopFlashSaleCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToFlashSale={() => handleSelectView('marketing-shop-flash-sale')} />
            ) : activeView === 'marketing-shop-flash-sale-detail' ? (
              <ShopFlashSaleDetailView runId={run?.id ?? null} campaignId={activeFlashSaleCampaignId} readOnly={readOnly} onBackToFlashSale={() => handleSelectView('marketing-shop-flash-sale')} />
            ) : activeView === 'marketing-shop-flash-sale-data' ? (
              <ShopFlashSaleDataView runId={run?.id ?? null} campaignId={activeFlashSaleCampaignId} readOnly={readOnly} onBackToFlashSale={() => handleOpenFlashSaleDetail(activeFlashSaleCampaignId || 0)} />
            ) : activeView === 'marketing-shop-flash-sale' ? (
              <ShopFlashSaleView runId={run?.id ?? null} readOnly={readOnly} onCreate={() => handleSelectView('marketing-shop-flash-sale-create')} onDetail={handleOpenFlashSaleDetail} onData={handleOpenFlashSaleData} />
            ) : activeView === 'marketing-shopee-ads' ? (
              <ShopeeAdsView readOnly={readOnly} />
            ) : activeView === 'marketing-shipping-fee-promotion' ? (
              <ShippingFeePromotionView
                runId={run?.id ?? null}
                readOnly={readOnly}
                onCreate={() => handleSelectView('marketing-shipping-fee-promotion-create')}
                onEdit={(promotionId) => handleSelectView('marketing-shipping-fee-promotion-update', promotionId)}
              />
            ) : activeView === 'marketing-shipping-fee-promotion-create' ? (
              <ShippingFeePromotionCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToShippingFeePromotion={() => handleSelectView('marketing-shipping-fee-promotion')} />
            ) : activeView === 'marketing-shipping-fee-promotion-update' ? (
              <ShippingFeePromotionCreateView
                runId={run?.id ?? null}
                campaignId={activeShippingFeePromotionId}
                readOnly={readOnly}
                onBackToShippingFeePromotion={() => handleSelectView('marketing-shipping-fee-promotion')}
              />
            ) : activeView === 'marketing-voucher-orders' ? (
              <VoucherOrdersView
                runId={run?.id ?? null}
                voucherType={activeVoucherCampaign?.voucherType ?? null}
                campaignId={activeVoucherCampaign?.campaignId ?? null}
                readOnly={readOnly}
              />
            ) : activeView === 'marketing-voucher-detail' && activeVoucherCampaign?.voucherType === 'product_voucher' ? (
              <ProductVoucherDetailView runId={run?.id ?? null} campaignId={activeVoucherCampaign.campaignId} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-voucher-detail' && activeVoucherCampaign?.voucherType === 'private_voucher' ? (
              <PrivateVoucherDetailView runId={run?.id ?? null} campaignId={activeVoucherCampaign.campaignId} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-voucher-detail' && activeVoucherCampaign?.voucherType === 'live_voucher' ? (
              <LiveVoucherDetailView runId={run?.id ?? null} campaignId={activeVoucherCampaign.campaignId} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-voucher-detail' && activeVoucherCampaign?.voucherType === 'video_voucher' ? (
              <VideoVoucherDetailView runId={run?.id ?? null} campaignId={activeVoucherCampaign.campaignId} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-voucher-detail' && activeVoucherCampaign?.voucherType === 'follow_voucher' ? (
              <FollowVoucherDetailView runId={run?.id ?? null} campaignId={activeVoucherCampaign.campaignId} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-voucher-detail' ? (
              <ShopVoucherDetailView runId={run?.id ?? null} campaignId={activeVoucherCampaign?.campaignId ?? null} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-voucher-create' ? (
              <ShopVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-private-voucher-create' ? (
              <PrivateVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-live-voucher-create' ? (
              <LiveVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-video-voucher-create' ? (
              <VideoVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-follow-voucher-create' ? (
              <FollowVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-product-voucher-create' ? (
              <ProductVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
            ) : activeView === 'marketing-vouchers' ? (
              <ShopVoucherView
                runId={run?.id ?? null}
                readOnly={readOnly}
                onCreateShopVoucher={() => handleSelectView('marketing-voucher-create')}
                onCreatePrivateVoucher={() => handleSelectView('marketing-private-voucher-create')}
                onCreateLiveVoucher={() => handleSelectView('marketing-live-voucher-create')}
                onCreateVideoVoucher={() => handleSelectView('marketing-video-voucher-create')}
                onCreateFollowVoucher={() => handleSelectView('marketing-follow-voucher-create')}
                onCreateProductVoucher={() => handleSelectView('marketing-product-voucher-create')}
                onOpenVoucherDetail={handleOpenVoucherDetail}
                onOpenVoucherOrders={handleOpenVoucherOrders}
              />
            ) : activeView === 'marketing-discount' ? (
              <MarketingDiscountView runId={run?.id ?? null} publicId={currentUser?.public_id ?? ''} readOnly={readOnly} />
            ) : activeView === 'marketing-centre' ? (
              <MarketingCentreView runId={run?.id ?? null} readOnly={readOnly} />
            ) : (
              <Dashboard />
            )}
          </div>
          <NotificationDrawer
            open={notificationDrawerOpen}
            loading={notificationLoading}
            orders={notificationOrders}
          />
          <ChatMessagesDrawer
            open={chatMessagesDrawerOpen}
            runId={run?.id ?? null}
            readOnly={readOnly}
            onOpenWebVersion={() => {
              handleSelectView('customer-service-web');
              setChatMessagesDrawerOpen(false);
            }}
            onUnreadCountChange={setChatUnreadCount}
          />
          {activeView !== 'customer-service-web' && (
            <RightSidebar
              notificationOpen={notificationDrawerOpen}
              chatMessagesOpen={chatMessagesDrawerOpen}
              onToggleNotification={() => {
                setNotificationDrawerOpen((prev) => !prev);
                setChatMessagesDrawerOpen(false);
              }}
              onToggleChatMessages={() => {
                setChatMessagesDrawerOpen((prev) => !prev);
                setNotificationDrawerOpen(false);
              }}
              notificationCount={notificationCount}
              chatUnreadCount={chatUnreadCount}
            />
          )}
        </div>
      </div>
    </div>
  );
}

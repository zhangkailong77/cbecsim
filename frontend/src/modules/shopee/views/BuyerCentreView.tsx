import React, { useEffect, useState } from 'react';
import { Search, ShoppingCart, ChevronDown, Star } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ACCESS_TOKEN_KEY = 'cbec_access_token';

const fallbackCategories = [
  '卫生纸', '医疗用口罩', '抽取式卫生纸', 'iPhone满版保护贴', '纯水湿纸巾', '豆腐砂',
  '宠物尿布吸收垫', '猫罐头',
  '男生四角裤', '抛弃式口罩',
  '环保垃圾袋', '舒肥鸡胸肉',
  '防滑晒衣架', '自动折叠伞',
  '彩色口罩', '自然假睫毛',
  'Medimix 香皂', '指甲贴片',
  'Ciao 猫肉泥', '苹果充电线'
];

interface BuyerCentreProduct {
  listing_id: number;
  rank: number;
  is_mall: boolean;
  title: string;
  category: string | null;
  cover_url: string | null;
  display_price: string;
  sales_count: number;
  rating: number;
  review_count: number;
}

interface BuyerCentreCategory {
  name: string;
  count: number;
}

interface BuyerCentreResponse {
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  categories: BuyerCentreCategory[];
  items: BuyerCentreProduct[];
}

interface BuyerCentreViewProps {
  runId: number | null;
  readOnly?: boolean;
  onOpenProductDetail: (listingId: number) => void;
  onBackToSellerCentre: () => void;
}

function resolveImageUrl(raw: string | null): string | null {
  if (!raw) return null;
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
  return `${API_BASE_URL}${raw.startsWith('/') ? '' : '/'}${raw}`;
}

function formatCount(value: number): string {
  return String(Math.max(0, Math.trunc(value || 0)));
}

function normalizePrice(value: string): string {
  const trimmed = String(value || '').trim();
  return trimmed || '0';
}

export default function BuyerCentreView({ runId, onOpenProductDetail, onBackToSellerCentre }: BuyerCentreViewProps) {
  const [activeTab, setActiveTab] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [jumpPage, setJumpPage] = useState('1');
  const [products, setProducts] = useState<BuyerCentreProduct[]>([]);
  const [categories, setCategories] = useState<BuyerCentreCategory[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setJumpPage(String(page));
  }, [page]);

  useEffect(() => {
    if (!runId) {
      setProducts([]);
      setCategories([]);
      setTotalPages(1);
      setError('暂无可读取的对局');
      return;
    }

    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!token) {
      setProducts([]);
      setCategories([]);
      setTotalPages(1);
      setError('请先登录后查看买家中心');
      return;
    }

    const params = new URLSearchParams({
      page: String(page),
      page_size: '10',
    });
    if (keyword.trim()) params.set('keyword', keyword.trim());
    if (activeTab.trim()) params.set('category', activeTab.trim());

    let ignore = false;
    setLoading(true);
    setError('');
    fetch(`${API_BASE_URL}/shopee/runs/${runId}/buyer-centre/products?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error('load buyer centre products failed');
        return res.json() as Promise<BuyerCentreResponse>;
      })
      .then((payload) => {
        if (ignore) return;
        setProducts(payload.items || []);
        setCategories(payload.categories || []);
        setTotalPages(Math.max(1, payload.meta?.total_pages || 1));
      })
      .catch(() => {
        if (ignore) return;
        setProducts([]);
        setError('商品加载失败，请稍后重试');
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [runId, keyword, activeTab, page]);

  const allCategories = categories.length > 0 ? categories.map((item) => item.name) : fallbackCategories;

  const handleSearch = () => {
    setKeyword(searchInput.trim());
    setPage(1);
  };

  const handleCategoryChange = (category: string) => {
    setActiveTab(category === activeTab ? '' : category);
    setPage(1);
  };

  const goToPage = (nextPage: number) => {
    setPage(Math.min(Math.max(1, nextPage), totalPages));
  };

  const handleJump = () => {
    const parsed = Number(jumpPage);
    if (!Number.isFinite(parsed)) return;
    goToPage(Math.trunc(parsed));
  };

  return (
    <div className="fixed inset-0 bg-[#f5f5f5] overflow-y-auto">
      {/* 顶部橙色大背景 */}
      <header className="bg-[#ee4d2d] w-full">
        <div className="max-w-[1200px] mx-auto px-4">
          <nav className="flex items-center justify-between py-1.5 text-[13px] text-white">
            <div className="flex items-center gap-2.5 font-light"></div>
            <div className="flex items-center gap-4 font-light">
              <div className="flex items-center gap-2.5 font-medium ml-1">
                <button type="button" onClick={onBackToSellerCentre} className="hover:text-white/80 transition">返回卖家中心</button>
              </div>
            </div>
          </nav>

          <div className="flex items-start py-4 gap-10">
            <a href="#" className="flex items-center gap-2.5 mt-0.5 shrink-0 text-white hover:opacity-90 transition-opacity">
              <svg viewBox="0 0 40 44" className="h-[46px] w-auto fill-current" xmlns="http://www.w3.org/2000/svg">
                <path d="M25.914134 32.7635637c-.249117 2.0382156-1.4950636 3.6705591-3.4249956 4.4880861-1.0746788.4552057-2.5177827.7009698-3.659991.6239878-1.7820188-.0675851-3.4559541-.4971301-4.9989944-1.282491-.5512798-.2804602-1.3730398-.8410192-2.0039791-1.3659785-.1598621-.1326403-.1788717-.2175735-.0731419-.3662969.05721-.0854754.1623968-.2392586.3952197-.577365.3374665-.4900825.3796498-.5517042.4176691-.6091696.1079024-.1642644.2833343-.1785404.4564126-.0435509.0182855.0140953.0182855.0140953.0320449.0247571.0282429.0216851.0282429.0216851.0952293.0733678.0678916.0522249.1080834.0831261.1243774.0954143 1.6639779 1.2918879 3.6022379 2.0371314 5.5589643 2.1115835 2.7221817-.0366839 4.6798134-1.2501442 5.0304962-3.1132529.3858053-2.0506845-1.2379807-3.8218124-4.4149456-4.8090251-.993571-.3088315-3.5050171-1.3052603-3.9679473-1.5745165-2.1747038-1.2646009-3.1914485-2.92134-3.0467941-4.9675068.2214172-2.8364068 2.8776987-4.9519659 6.2338974-4.9658804 1.5010381-.0030721 2.9988173.3059401 4.4377572.9071586.5094586.2128751 1.4192061.7034997 1.7331368.9358914.1808633.1317368.216529.2851586.1129717.4508687-.0579342.0957757-.1537066.2481133-.3552089.5652574l-.0023536.0036142c-.265773.4179796-.27392.4309907-.3349319.5287542-.1051867.1588431-.2288399.1738419-.4189364.0543934-1.5396005-1.0253423-3.2464859-1.5412662-5.123734-1.5784922-2.3371005.0459-4.0887038 1.4245282-4.204029 3.3028164-.0304154 1.6964951 1.2530074 2.9348932 4.0255194 3.8790971 5.6279422 1.792813 7.7816449 3.8946381 7.3762868 7.2084778M18.9638444 3.47806106c3.6639739 0 6.6506613 3.44702216 6.7904275 7.76162774h-13.580674c.1395851-4.31460558 3.1262725-7.76162774 6.7902465-7.76162774m18.962577 8.57282994c0-.4479773-.36408-.8112022-.8128888-.8112022h-8.8025535C28.0948122 5.54266018 23.9927111 1 18.9638444 1c-5.0288668 0-9.1309679 4.54266018-9.34713476 10.2396888l-8.8150456.0001807c-.44192907.0079512-.79786211.3679233-.79786211.8110215 0 .0211429.00090522.0421052.00235358.0628867H0l1.25662829 27.4585357c0 .0762592.00289671.1534219.00869013.230946.00126731.0175288.00271566.0348768.00416402.0522249l.00271566.0580075.00289671.0030721c.1910017 1.9106351 1.58974975 3.4493714 3.49198192 3.5203899l.00434506.0043371H32.7338906c.0132163.0001807.0264325.0001807.0398298.0001807.0132162 0 .0264324 0 .0396487-.0001807h.0595635l.0012674-.0010843c1.9351822-.0524056 3.5028445-1.6128269 3.6685-3.5471349l.0009053-.0009035.0012673-.0260221c.0016294-.0202394.0030777-.0406595.004345-.0608989.0030778-.0487914.0050693-.0972214.0057934-.1456514l1.3712294-27.566961h-.0009053c.0007242-.0137339.0010863-.0278292.0010863-.0417438"></path>
              </svg>
              <span className="text-[32px] font-semibold tracking-widest font-sans">虾皮购物</span>
            </a>

            <div className="flex-1 flex flex-col gap-1.5 ml-2">
              <div className="flex bg-white rounded-sm p-1 shadow-sm">
                <input
                  type="text"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') handleSearch();
                  }}
                  placeholder="搜索可查看商品"
                  className="w-full px-3 text-sm text-gray-800 outline-none placeholder:text-[#ee4d2d]"
                />
                <button type="button" onClick={handleSearch} className="bg-[#fb5533] hover:bg-[#f04d2d] transition-colors px-6 py-2 rounded-sm text-white">
                  <Search size={16} strokeWidth={2.5} />
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[12px] text-white">
                <a href="#" className="hover:text-white/80">隔日到货手机壳</a>
                <a href="#" className="hover:text-white/80">流行衣服</a>
              </div>
            </div>

            <a href="#" className="mt-2 shrink-0 px-4 hover:opacity-80 transition-opacity text-white">
              <ShoppingCart size={28} strokeWidth={1.5} />
            </a>
          </div>
        </div>
      </header>

      {/* ===================== 下方主体内容 ===================== */}
      <main className="max-w-[1200px] mx-auto pb-20">

        <div className="py-8 text-center">
          <h2 className="text-[20px] font-medium text-gray-500 uppercase tracking-widest">
            全部商品
          </h2>
        </div>

        {/* 2. 导航 Tabs 区域 */}
        <div className="sticky top-0 z-50 bg-white flex items-stretch shadow-sm h-[52px]">

          <div className="flex flex-1">
            {allCategories.slice(0, 6).map((category) => (
              <button
                key={category}
                onClick={() => handleCategoryChange(category)}
                className={`flex-1 flex items-center justify-center text-sm font-medium transition-colors border-b-4 ${
                  activeTab === category
                    ? 'text-[#ee4d2d] border-[#ee4d2d]'
                    : 'text-gray-700 border-transparent hover:text-[#ee4d2d]'
                }`}
              >
                {category}
              </button>
            ))}
          </div>

          <div className="relative group flex items-stretch cursor-pointer">
            <div className="flex items-center gap-1 px-6 text-sm font-medium text-gray-700 group-hover:text-[#ee4d2d] transition-colors border-b-4 border-transparent">
              查看更多 <ChevronDown size={14} className="transition-transform duration-200 group-hover:rotate-180" />
            </div>

            {/* 下拉面板（包含平滑的淡入上滑动画） */}
            <div className="absolute top-full right-[-100px] mt-[1px] w-[460px] opacity-0 invisible translate-y-2 group-hover:opacity-100 group-hover:visible group-hover:translate-y-0 transition-all duration-200 ease-out">
              <div className="bg-white rounded-sm shadow-[0_2px_16px_rgba(0,0,0,0.1)] border border-gray-100 p-6 relative">
                <div className="absolute -top-1.5 right-[150px] w-3 h-3 bg-white border-t border-l border-gray-100 rotate-45"></div>
                <div className="relative z-10 grid grid-cols-2 gap-y-4 gap-x-6">
                  {allCategories.map((category) => (
                    <div
                      key={category}
                      onClick={() => handleCategoryChange(category)}
                      className={`text-sm cursor-pointer transition-colors hover:text-[#ee4d2d] ${
                        activeTab === category ? 'text-[#ee4d2d]' : 'text-gray-700'
                      }`}
                    >
                      {category}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

        </div>

        {loading && (
          <div className="py-10 text-center text-sm text-gray-400">商品加载中...</div>
        )}

        {!loading && error && (
          <div className="py-10 text-center text-sm text-gray-400">{error}</div>
        )}

        {!loading && !error && products.length === 0 && (
          <div className="py-10 text-center text-sm text-gray-400">
            {keyword || activeTab ? '没有找到符合条件的商品' : '暂无上架商品'}
          </div>
        )}

        {/* 3. 商品卡片网格布局 (5列) */}
        {!loading && !error && products.length > 0 && (
          <div className="grid grid-cols-5 gap-2.5 mt-2.5">
            {products.map((product) => (
              <button
                type="button"
                key={product.listing_id}
                onClick={() => onOpenProductDetail(product.listing_id)}
                className="bg-white relative flex flex-col group cursor-pointer transition-transform hover:-translate-y-[1px] shadow-sm hover:shadow-md border-2 border-transparent hover:border-[#ee4d2d] text-left"
              >
                <div className="absolute top-0 left-0 z-10 w-8 h-10 bg-gradient-to-br from-[#ffb429] to-[#f53d2d] flex flex-col items-center justify-center text-white rounded-br-lg shadow-sm">
                  <span className="text-[10px] leading-tight font-bold">TOP</span>
                  <span className="text-[14px] leading-tight font-bold">{product.rank}</span>
                </div>

                <div className="w-full aspect-square bg-gray-100 flex items-center justify-center text-gray-300 relative overflow-hidden">
                  {resolveImageUrl(product.cover_url) ? (
                    <img src={resolveImageUrl(product.cover_url) || ''} alt={product.title} className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-xs">商品主图 {product.listing_id}</span>
                  )}
                  <div className="absolute inset-0 bg-white/0 group-hover:bg-white/5 transition-colors" />
                </div>

                <div className="p-3 flex flex-col flex-1">
                  <div className="text-sm text-gray-800 line-clamp-2 h-10 leading-5">
                    {product.is_mall && (
                      <span className="inline-block bg-[#ee4d2d] text-white text-[10px] px-1 rounded-sm mr-1 font-medium transform -translate-y-px">
                        商城
                      </span>
                    )}
                    {product.title}
                  </div>

                  <div className="mt-auto pt-3">
                    <div className="text-[#ee4d2d] text-base font-medium flex items-baseline">
                      <span className="text-xs mr-0.5">$</span>
                      {normalizePrice(product.display_price)}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-gray-400 mt-1.5">
                      <span>{formatCount(product.sales_count)}已售</span>
                      <div className="flex items-center gap-1">
                        <div className="flex items-center text-[#ffce3d]">
                          {[...Array(5)].map((_, i) => (
                            <Star key={i} size={10} className="fill-current" />
                          ))}
                        </div>
                        <span>({formatCount(product.review_count)})</span>
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* 4. 底部翻页器 (Pagination) */}
        <div className="flex justify-center items-center mt-12 mb-8 text-[14px] text-gray-600">

          {/* 页码与箭头 */}
          <div className="flex items-center gap-6">
            <button type="button" disabled={page <= 1} onClick={() => goToPage(page - 1)} className={`${page <= 1 ? 'text-gray-300 cursor-not-allowed hover:text-gray-300' : 'hover:text-[#ee4d2d]'} text-lg font-light transition-colors`}>
              &lt;
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((pageNo) => (
              <button key={pageNo} type="button" onClick={() => goToPage(pageNo)} className={pageNo === page ? 'text-[#ee4d2d] font-medium text-base' : 'hover:text-[#ee4d2d] transition-colors text-base'}>
                {pageNo}
              </button>
            ))}
            <button type="button" disabled={page >= totalPages} onClick={() => goToPage(page + 1)} className={`${page >= totalPages ? 'text-gray-300 cursor-not-allowed hover:text-gray-300' : 'hover:text-[#ee4d2d]'} text-lg font-light transition-colors`}>
              &gt;
            </button>
          </div>

          {/* 跳转表单 */}
          <div className="flex items-center gap-2 ml-8">
            <span>跳转至</span>
            <input
              type="text"
              value={jumpPage}
              onChange={(event) => setJumpPage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') handleJump();
              }}
              className="w-12 h-[30px] border border-gray-200 rounded-[3px] text-center text-gray-700 outline-none focus:border-gray-400 focus:shadow-sm transition-shadow"
            />
            <span>页</span>
            <button type="button" onClick={handleJump} className="h-[30px] px-3.5 border border-gray-200 rounded-[3px] hover:border-gray-300 hover:bg-gray-50 transition-colors bg-white shadow-sm">
              Go
            </button>
          </div>

        </div>

      </main>
    </div>
  );
}

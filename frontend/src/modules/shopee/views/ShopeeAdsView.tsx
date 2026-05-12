import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from 'lucide-react';

interface ShopeeAdsViewProps {
  readOnly?: boolean;
}

// ---------------- 常用图标组件 ----------------
const InfoIcon = ({ tooltipText }: { tooltipText?: string }) => {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const iconRef = useRef<HTMLDivElement>(null);

  const updatePosition = () => {
    if (!iconRef.current) return;
    const rect = iconRef.current.getBoundingClientRect();
    setPos({
      x: rect.left + rect.width / 2,
      y: rect.top - 8
    });
  };

  const handleMouseEnter = () => {
    if (!tooltipText) return;
    updatePosition();
    setShow(true);
  };

  useEffect(() => {
    if (show) {
      window.addEventListener('scroll', updatePosition, true);
      window.addEventListener('resize', updatePosition);
      return () => {
        window.removeEventListener('scroll', updatePosition, true);
        window.removeEventListener('resize', updatePosition);
      };
    }
  }, [show]);

  const iconSvg = (
    <svg viewBox="0 0 1024 1024" className={`w-3.5 h-3.5 fill-current transition-colors ${tooltipText && show ? 'text-[#ee4d2d]' : 'text-[#b2b2b2]'}`}>
      <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path>
      <path d="M464 688h96v-96h-96v96zm48-392c-65.3 0-118.3 49.3-126.9 113.1l74 15.6c4.5-33.6 34.3-56.7 60.9-56.7 34.1 0 64 25.1 64 60 0 25.5-16.7 44.5-44.1 61.2l-23.9 14.6V560h80v-34.5l22.4-13.6c39-23.7 61.6-58.1 61.6-99.9 0-64-57.3-116-128-116z"></path>
    </svg>
  );

  if (!tooltipText) return <span className="inline-block ml-1">{iconSvg}</span>;

  const tooltipNode = show && typeof document !== 'undefined' ? createPortal(
    <div
      className="fixed z-[9999] w-max max-w-[280px] bg-white border border-[#ebebeb] shadow-[0_4px_16px_rgba(0,0,0,0.12)] rounded-sm px-4 py-3 text-[12px] text-[#555] font-normal whitespace-normal leading-relaxed pointer-events-none transform -translate-x-1/2 -translate-y-full text-left"
      style={{ left: pos.x, top: pos.y }}
    >
      {tooltipText}
      <div className="absolute -bottom-[5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-white border-b border-r border-[#ebebeb] transform rotate-45"></div>
    </div>,
    document.body
  ) : null;

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
      {tooltipNode}
    </>
  );
};

const CheckCircleIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="#26b562" className="mr-1.5 inline-block flex-shrink-0">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="#fff"></path>
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M10 17.41L4.59 12 6 10.59l4 4 8-8L19.41 8 10 17.41z" fill="#fff"></path>
  </svg>
);

const WarningIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="#ffb537" className="inline-block flex-shrink-0">
    <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"></path>
  </svg>
);

const ToastWarningIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" className="flex-shrink-0">
    <circle cx="12" cy="12" r="12" fill="#ffb537" />
    <path d="M11 6h2v8h-2V6zm0 10h2v2h-2v-2z" fill="#fff" />
  </svg>
);

const SortIcon = () => (
  <div className="inline-flex flex-col ml-1 w-2 cursor-pointer opacity-40 hover:opacity-100">
    <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="3" fill="none" className="-mb-[3px]"><polyline points="18 15 12 9 6 15"></polyline></svg>
    <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" strokeWidth="3" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
  </div>
);

const ChevronDownIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>;
const ChevronRightIcon = () => <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><polyline points="9 18 15 12 9 6"></polyline></svg>;
const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" width="1em" height="1em" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="mr-1">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    <polyline points="9 12 11 14 15 10"></polyline>
  </svg>
);

// ---------------- 图表数据与算法配置 ----------------
const chartMax = {
  '曝光量': 120000,
  '点击数': 80,
  '点击率 (CTR)': 8,
  '订单数': 100,
  '售出商品数': 120,
  '销售额': 2000,
  '花费': 120,
  '投入产出比 (ROAS)': 15,
};

const mockChartData =[
  { date: '01/02', '曝光量': 80000, '点击数': 25, '点击率 (CTR)': 2.1, '订单数': 40, '售出商品数': 45, '销售额': 300, '花费': 40, '投入产出比 (ROAS)': 7.5 },
  { date: '03/02', '曝光量': 75000, '点击数': 20, '点击率 (CTR)': 1.8, '订单数': 35, '售出商品数': 38, '销售额': 250, '花费': 35, '投入产出比 (ROAS)': 7.1 },
  { date: '05/02', '曝光量': 70000, '点击数': 18, '点击率 (CTR)': 1.5, '订单数': 30, '售出商品数': 32, '销售额': 220, '花费': 30, '投入产出比 (ROAS)': 7.3 },
  { date: '07/02', '曝光量': 90000, '点击数': 35, '点击率 (CTR)': 2.8, '订单数': 50, '售出商品数': 55, '销售额': 500, '花费': 50, '投入产出比 (ROAS)': 10.0 },
  { date: '09/02', '曝光量': 85000, '点击数': 30, '点击率 (CTR)': 2.5, '订单数': 45, '售出商品数': 48, '销售额': 450, '花费': 45, '投入产出比 (ROAS)': 10.0 },
  { date: '11/02', '曝光量': 82000, '点击数': 28, '点击率 (CTR)': 2.2, '订单数': 42, '售出商品数': 45, '销售额': 400, '花费': 42, '投入产出比 (ROAS)': 9.5 },
  { date: '13/02', '曝光量': 110000, '点击数': 55, '点击率 (CTR)': 4.5, '订单数': 70, '售出商品数': 75, '销售额': 800, '花费': 70, '投入产出比 (ROAS)': 11.4 },
  { date: '15/02', '曝光量': 78000, '点击数': 22, '点击率 (CTR)': 1.9, '订单数': 35, '售出商品数': 38, '销售额': 300, '花费': 35, '投入产出比 (ROAS)': 8.5 },
  { date: '17/02', '曝光量': 65000, '点击数': 15, '点击率 (CTR)': 1.4, '订单数': 25, '售出商品数': 28, '销售额': 200, '花费': 25, '投入产出比 (ROAS)': 8.0 },
  { date: '19/02', '曝光量': 72000, '点击数': 18, '点击率 (CTR)': 1.6, '订单数': 28, '售出商品数': 30, '销售额': 250, '花费': 28, '投入产出比 (ROAS)': 8.9 },
  { date: '21/02', '曝光量': 92000, '点击数': 35, '点击率 (CTR)': 2.9, '订单数': 55, '售出商品数': 60, '销售额': 500, '花费': 55, '投入产出比 (ROAS)': 9.0 },
  { date: '23/02', '曝光量': 98000, '点击数': 40, '点击率 (CTR)': 3.2, '订单数': 60, '售出商品数': 65, '销售额': 600, '花费': 60, '投入产出比 (ROAS)': 10.0 },
  { date: '25/02', '曝光量': 95000, '点击数': 38, '点击率 (CTR)': 3.0, '订单数': 58, '售出商品数': 62, '销售额': 550, '花费': 58, '投入产出比 (ROAS)': 9.4 },
  { date: '26/02', '曝光量': 101400, '点击数': 33, '点击率 (CTR)': 3.38, '订单数': 74, '售出商品数': 80, '销售额': 977, '花费': 17, '投入产出比 (ROAS)': 8.24 },
  { date: '01/03', '曝光量': 115000, '点击数': 60, '点击率 (CTR)': 5.0, '订单数': 80, '售出商品数': 90, '销售额': 1200, '花费': 80, '投入产出比 (ROAS)': 15.0 },
  { date: '03/03', '曝光量': 75000, '点击数': 25, '点击率 (CTR)': 2.1, '订单数': 35, '售出商品数': 40, '销售额': 400, '花费': 35, '投入产出比 (ROAS)': 11.4 },
  { date: '05/03', '曝光量': 80000, '点击数': 30, '点击率 (CTR)': 2.5, '订单数': 40, '售出商品数': 45, '销售额': 450, '花费': 40, '投入产出比 (ROAS)': 11.2 },
  { date: '07/03', '曝光量': 78000, '点击数': 28, '点击率 (CTR)': 2.3, '订单数': 38, '售出商品数': 42, '销售额': 420, '花费': 38, '投入产出比 (ROAS)': 11.0 },
  { date: '09/03', '曝光量': 95000, '点击数': 45, '点击率 (CTR)': 3.8, '订单数': 60, '售出商品数': 65, '销售额': 700, '花费': 60, '投入产出比 (ROAS)': 11.6 },
  { date: '11/03', '曝光量': 92000, '点击数': 42, '点击率 (CTR)': 3.5, '订单数': 58, '售出商品数': 62, '销售额': 650, '花费': 58, '投入产出比 (ROAS)': 11.2 },
  { date: '13/03', '曝光量': 118000, '点击数': 65, '点击率 (CTR)': 5.5, '订单数': 90, '售出商品数': 95, '销售额': 1400, '花费': 90, '投入产出比 (ROAS)': 15.5 },
  { date: '15/03', '曝光量': 88000, '点击数': 35, '点击率 (CTR)': 2.9, '订单数': 45, '售出商品数': 50, '销售额': 500, '花费': 45, '投入产出比 (ROAS)': 11.1 },
  { date: '17/03', '曝光量': 105000, '点击数': 50, '点击率 (CTR)': 4.2, '订单数': 65, '售出商品数': 70, '销售额': 800, '花费': 65, '投入产出比 (ROAS)': 12.3 },
  { date: '19/03', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '21/03', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '24/03', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '27/03', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '30/03', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '02/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '05/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '08/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '11/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '14/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '17/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
  { date: '19/04', '曝光量': 0, '点击数': 0, '点击率 (CTR)': 0, '订单数': 0, '售出商品数': 0, '销售额': 0, '花费': 0, '投入产出比 (ROAS)': 0 },
];

export default function ShopeeAdsView({ readOnly = false }: ShopeeAdsViewProps) {
  const [activeTab, setActiveTab] = useState('全部点击出价广告');
  const [listTab, setListTab] = useState('全部');

  const [recIndex, setRecIndex] = useState(0);

  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['点击数', '点击率 (CTR)', '销售额', '花费']);
  const[toastMsg, setToastMsg] = useState<string | null>(null);
  const toastTimeoutRef = useRef<number | null>(null);

  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    toastTimeoutRef.current = window.setTimeout(() => {
      setToastMsg(null);
    }, 3000);
  };

  const toggleMetric = (label: string) => {
    if (selectedMetrics.includes(label)) {
      if (selectedMetrics.length > 1) {
        setSelectedMetrics(selectedMetrics.filter(m => m !== label));
      }
    } else {
      if (selectedMetrics.length >= 4) {
        showToast('您每次最多只能选择 4 个指标');
      } else {
        setSelectedMetrics([...selectedMetrics, label]);
      }
    }
  };

  const recommendationsData =[
    {
      id: 1,
      title: '开启大促日激增优化，提升销量！',
      desc: '解锁 15% 销量增长和 15% 订单增长！让 Shopee 在大促日通过优化投资回报率 (ROI)、预算和手动出价，最大化您的销售额。',
      btnText: '立即开启',
      icon: <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>,
    },
    {
      id: 2,
      title: '开启自动增加预算，获得更好表现！',
      desc: '自动提高表现优异广告的日预算。避免预算不足，让高潜力广告获得充分曝光。',
      btnText: '立即采纳',
      icon: <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline></svg>,
    },
    {
      id: 3,
      title: '创建自动选择商品广告以提升 GMV！',
      desc: '“自动选择商品”功能会在全店范围内识别高潜力商品并战略性地分配广告预算，最大化您的销售额。',
      btnText: '立即创建',
      icon: <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>,
    },
    {
      id: 4,
      title: '新功能“ROAS 保护”现已上线',
      desc: '恭喜！ROAS 保护现已适用于符合条件的 GMV Max 自定义 ROAS 广告。如果实际 ROAS 低于设定阈值，平台将提供返点。',
      btnText: '我了解了',
      icon: <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>,
    }
  ];

  const performanceMetrics =[
    { label: '曝光量', value: '101.4k', baseColor: '#4a90e2', tooltip: '买家看到您广告的次数。' },
    { label: '点击数', value: '4.1k', baseColor: '#f5a623', tooltip: '买家点击您广告的次数。（注意：Shopee 会过滤掉同一买家在短时间内产生的重复点击。）' },
    { label: '点击率 (CTR)', value: '4.09%', baseColor: '#50e3c2', tooltip: '点击率 (CTR) 衡量买家看到广告后点击广告的频率。它是您的广告被点击的次数除以被看到的次数。CTR = 点击数 ÷ 曝光量 × 100%。' },
    { label: '订单数', value: '74', baseColor: '#9013fe', tooltip: '买家在点击您的广告后 7 天内产生的订单数量。' },
    { label: '售出商品数', value: '80', baseColor: '#2673dd', tooltip: '买家在点击您的广告后 7 天内购买的商品总数量。' },
    { label: '销售额', value: 'RM 44.4k', baseColor: '#f37021', tooltip: '买家在点击您的广告后 7 天内产生的所有订单的总销售额（不包含卖家返点）。' },
    { label: '花费', value: 'RM 5.4k', baseColor: '#ee4d2d', tooltip: '您在广告上的花费金额。' },
    { label: '投入产出比 (ROAS)', value: '8.24', baseColor: '#555555', tooltip: '投入产出比 (ROAS) 衡量买家点击您的广告后 7 天内产生的订单销售额与广告花费的相对比例（ROAS = 销售额 ÷ 花费）。' },
  ];

  const svgWidth = 1000;
  const svgHeight = 240;
  const pointSpacing = svgWidth / (mockChartData.length - 1);

  const getSmoothPath = (key: string) => {
    const points = mockChartData.map((d, i) => {
      const val = d[key as keyof typeof d] as number;
      const maxVal = chartMax[key as keyof typeof chartMax];
      const normalizedY = svgHeight - (val / maxVal) * svgHeight;
      return { x: i * pointSpacing, y: normalizedY };
    });

    let d = `M ${points[0].x} ${points[0].y} `;
    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];
      const cp1x = p1.x + (p2.x - p1.x) / 2;
      d += `C ${cp1x} ${p1.y}, ${cp1x} ${p2.y}, ${p2.x} ${p2.y} `;
    }
    return d;
  };

  const handleChartMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = x / rect.width;
    const index = Math.round(percent * (mockChartData.length - 1));
    setHoverIndex(Math.max(0, Math.min(mockChartData.length - 1, index)));
  };

  const formatTooltipValue = (key: string, value: number) => {
    if (key === '点击率 (CTR)') return `${value.toFixed(2)}%`;
    if (key === '销售额' || key === '花费') return `RM ${value}`;
    return value;
  };

  // 广告列表数据
  const adsList =[
    {
      id: 'A001',
      image: 'https://via.placeholder.com/48/f5f5f5/ff7337?text=Shop',
      name: '店铺广告 04-12-2024',
      type: '店铺广告 - 自动出价',
      period: '19/12/2024 - 23/12/2024',
      status: 'Ended',
      statusLabel: '已结束',
      hasWarning: false,
      roasProtected: false,
      budget: 'RM 100.00',
      targetRoas: '-',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
      ctr: '0%',
      conversions: '0',
      conversionRate: '0%',
      itemsSold: '0',
    },
    {
      id: 'A002',
      image: 'https://via.placeholder.com/48',
      name: '电竞电脑桌 加固加厚 坚固耐用...',
      type: '商品广告 - GMV Max 自定义 ROAS',
      period: '无结束日期',
      status: 'Paused',
      statusLabel: '暂停中',
      hasWarning: true,
      roasProtected: true,
      budget: 'RM 300.00',
      targetRoas: '8.4',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
      ctr: '0%',
      conversions: '0',
      conversionRate: '0%',
      itemsSold: '0',
    },
    {
      id: 'A003',
      image: 'https://via.placeholder.com/48',
      name: '厨房收纳置物架 多层碗碟沥水架...',
      type: '商品广告 - GMV Max 自定义 ROAS',
      period: '无结束日期',
      status: 'Paused',
      statusLabel: '暂停中',
      hasWarning: true,
      roasProtected: true,
      budget: 'RM 500.00',
      targetRoas: '8.4',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
      ctr: '0%',
      conversions: '0',
      conversionRate: '0%',
      itemsSold: '0',
    },
    {
      id: 'A004',
      image: 'https://via.placeholder.com/48',
      name: 'HomeNeat 厨房收纳架 不锈钢 2-3层...',
      type: '商品广告 - GMV Max 自动出价',
      period: '无结束日期',
      status: 'Paused',
      statusLabel: '暂停中',
      hasWarning: true,
      roasProtected: false,
      budget: 'RM 1,200.00',
      targetRoas: '6.51 ~ 10.51',
      diagnosis: '-',
      expense: 'RM 0.00',
      sales: 'RM 0.00',
      roas: '0.00',
      impressions: '0',
      clicks: '0',
      ctr: '0%',
      conversions: '0',
      conversionRate: '0%',
      itemsSold: '0',
    }
  ];

  const tableGridCols = "grid-cols-[minmax(350px,3fr)_repeat(12,minmax(130px,1fr))]";

  return (
    <div className="flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]">

      {/* 顶部居中报错 Toast 弹窗 */}
      {toastMsg && typeof document !== 'undefined' && createPortal(
        <div className="fixed top-[60px] left-1/2 -translate-x-1/2 z-[9999] flex items-center gap-3 bg-white px-6 py-3 shadow-[0_4px_24px_rgba(0,0,0,0.12)] border border-[#ebebeb] rounded-sm text-[#333] text-[14px] font-medium animate-in fade-in slide-in-from-top-4 duration-300">
          <ToastWarningIcon />
          {toastMsg}
        </div>,
        document.body
      )}

      <div className="mx-auto max-w-[1660px]">
        {readOnly && (
          <div className="mb-5 border border-amber-200 bg-amber-50 px-4 py-2 text-[13px] text-amber-700">
            当前为历史对局回溯模式：可浏览 Shopee 广告页，但无法创建或编辑广告。
          </div>
        )}

        {/* 顶部 Header */}
        <div className="bg-white px-6 py-4 flex items-center justify-between shadow-sm border border-[#ebebeb] rounded-sm mb-4 relative overflow-hidden">

          <div className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none z-0">
            <svg width="450" height="350" viewBox="0 0 400 320" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path opacity="0.05" d="M372.424 139.953C371.408 127.192 378.155 115.016 376.017 102.271C374.001 90.3241 365.528 82.3059 354.858 76.7374C335.531 66.6512 314.529 56.7365 299.807 40.2068C293.607 33.2513 289.559 25.0194 282.807 18.4909C275.246 11.1925 265.938 5.79952 255.709 2.79092C221.806 -7.24548 185.887 10.62 174.842 43.0122C165.306 71.0391 145.246 87.2553 116.259 97.0156C97.3365 101.94 75.1204 108.713 59.8798 142.274C44.6393 175.834 62.9565 210.296 74.7917 221.761C89.5732 236.081 106.817 244.406 125.621 249.483C157.211 258.015 189.565 265.503 218.364 280.059C259.017 300.605 293.724 310.608 342.583 296.237C366.515 289.198 389.181 263.644 397.049 232.417C404.917 201.191 387.807 189.761 382.763 175.612C378.623 163.981 373.438 152.33 372.424 139.953Z" fill="#EE4D2D"></path>
              <path fillRule="evenodd" clipRule="evenodd" d="M125.425 173.061C127.977 172.994 130.044 170.93 130.262 168.374L130.278 168.065L132.086 131.651V131.596C132.086 131.312 131.973 131.039 131.772 130.838C131.571 130.638 131.299 130.525 131.015 130.525H119.409C119.124 123 113.718 117 107.085 117C100.451 117 95.0456 123.001 94.7611 130.525H83.1378C82.857 130.53 82.5895 130.645 82.3928 130.845C82.1961 131.046 82.0859 131.315 82.0859 131.596V131.679L83.7344 167.95L83.7591 168.405C84.0109 170.929 85.8548 172.962 88.3635 173.055L125.237 173.06L125.425 173.061ZM107.085 120.273C111.916 120.273 115.856 124.826 116.038 130.525H98.1322C98.3163 124.826 102.254 120.273 107.085 120.273ZM109.542 142.271H114.452C115.325 142.271 116.158 142.311 116.952 142.39C117.765 142.449 118.529 142.588 119.243 142.807C119.977 143.025 120.672 143.352 121.326 143.789C121.981 144.225 122.606 144.81 123.201 145.544C123.875 146.377 124.381 147.32 124.719 148.371C125.076 149.423 125.254 150.563 125.254 151.793C125.254 152.924 125.086 154.015 124.748 155.067C124.431 156.118 123.915 157.09 123.201 157.983C122.626 158.697 122.011 159.272 121.356 159.709C120.721 160.145 120.037 160.482 119.303 160.72C118.569 160.959 117.795 161.117 116.982 161.197C116.188 161.276 115.345 161.316 114.452 161.316H109.542V142.271ZM99.359 142.271H96.3237L88.2297 161.316H92.4553L93.6753 158.34H102.037L103.257 161.316H107.453L99.359 142.271Z M 97.8 147 L 94.8 155.5 H 100.8 Z M 112.8 145.5 H 114.5 C 118.5 145.5 121.5 148 121.5 151.7 C 121.5 155.5 118.5 158 114.5 158 H 112.8 Z" fill="#FDEDEA"></path>
            </svg>
          </div>

          <div className="flex items-center gap-4 relative z-10">
            <h1 className="text-[20px] font-medium text-[#333]">Shopee 广告</h1>
            <span className="flex items-center gap-1.5 text-[13px] text-[#05a] cursor-pointer hover:underline font-medium border-l border-[#e5e5e5] pl-4">
              <span className="text-lg leading-none">🚀</span> 智能店铺助手 <ChevronRightIcon />
            </span>
          </div>

          <button
            disabled={readOnly}
            className="bg-[#ee4d2d] text-white px-6 py-2 rounded-sm text-[14px] hover:bg-[#d83f21] transition-colors disabled:bg-[#f3a899] disabled:cursor-not-allowed relative z-10"
          >
            + 创建新广告
          </button>
        </div>

        {/* 1. 账户总览三大卡片 */}
        <div className="grid grid-cols-3 gap-4 mb-4">

          {/* Card 1: 我的账户 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[16px] font-medium text-[#333]">我的账户</h2>
                <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">更多 <ChevronRightIcon /></span>
              </div>
              <div className="grid grid-cols-2 gap-4 mb-5">
                <div>
                  <div className="text-[13px] text-[#666]">广告余额 <InfoIcon tooltipText="您账户中目前可用于广告花费的金额" /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 73.63</div>
                </div>
                <div>
                  <div className="text-[13px] text-[#666]">今日花费 <InfoIcon tooltipText="今日截至目前产生的广告花费" /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
              </div>
              <button className="w-full bg-[#ee4d2d] text-white py-2 rounded-sm text-[14px] hover:bg-[#d83f21] transition-colors mb-4">充值</button>
            </div>
            <div className="space-y-2">
              <div className="bg-[#fff6f4] rounded-[2px] px-3 py-2.5 flex items-center justify-between cursor-pointer hover:bg-[#ffece8] transition-colors">
                <div className="flex items-start gap-2.5 text-[13px]">
                  <svg className="w-[18px] h-[18px] mt-0.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M19 4h-2V2h-2v2H9V2H7v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10z" fill="#ee4d2d"/>
                    <circle cx="17" cy="17" r="5" fill="#ee4d2d" stroke="#fff6f4" strokeWidth="1.5"/>
                    <path d="M17 14.5v5M15.5 17h3" stroke="#fff" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                  <div className="leading-[1.4] pr-2">
                    <span className="text-[#333] mr-1.5">开启自动充值 (卖家余额)</span>
                    <span className="text-[#ee4d2d]">销量最高提升 20% ↗</span>
                  </div>
                </div>
                <div className="flex-shrink-0 text-[#999]">
                  <ChevronRightIcon />
                </div>
              </div>

              <div className="bg-[#fff6f4] rounded-[2px] px-3 py-2.5 flex items-center justify-between cursor-pointer hover:bg-[#ffece8] transition-colors">
                <div className="flex items-start gap-2.5 text-[13px]">
                  <svg className="w-[18px] h-[18px] mt-0.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 7H3c-1.1 0-2 .9-2 2v8c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zm0 10H3V9h18v8z" fill="#ee4d2d"/>
                    <path d="M18 11h2v4h-2z" fill="#ee4d2d"/>
                    <circle cx="15" cy="15" r="5" fill="#ee4d2d" stroke="#fff6f4" strokeWidth="1.5"/>
                    <path d="M15 12.5v5M13.5 15h3" stroke="#fff" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                  <div className="leading-[1.4] pr-2">
                    <span className="text-[#333] mr-1.5">自动充值 (我的余额)</span>
                    <span className="text-[#ee4d2d]">保持广告投放</span>
                  </div>
                </div>
                <div className="flex-shrink-0 text-[#999]">
                  <ChevronRightIcon />
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: 智能代金券 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 flex flex-col justify-between relative">
            <div className="absolute top-0 left-0 bg-[#ee4d2d] text-white text-[12px] px-2 py-0.5 rounded-br-sm rounded-tl-sm font-medium">
              100% 平台赞助
            </div>
            <div className="flex-1 flex flex-col mb-4">
              <div className="flex items-center justify-between mb-4 mt-2">
                <h2 className="text-[16px] font-medium text-[#333]">智能代金券</h2>
                <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">设置 <ChevronRightIcon /></span>
              </div>
              <div className="flex-1 grid grid-cols-2 items-center border border-[#ebebeb] rounded-sm px-4 py-2">
                <div className="border-r border-[#ebebeb]">
                  <div className="text-[13px] text-[#666]">代金券金额 <InfoIcon tooltipText="平台免费赠送给您的智能代金券总额" /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
                <div className="pl-6">
                  <div className="text-[13px] text-[#666]">代金券促成销售额 <InfoIcon tooltipText="使用智能代金券带来的直接销售额" /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
              </div>
            </div>
            <div className="bg-[#f5f5f5] text-[#555] text-[13px] px-3 py-2 rounded-[2px] flex items-center">
              <CheckCircleIcon /> 通过平台赞助代金券提升广告效果
            </div>
          </div>

          {/* Card 3: ROAS 保护 */}
          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 flex flex-col justify-between">
            <div className="flex-1 flex flex-col mb-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[16px] font-medium text-[#333]">ROAS 保护</h2>
                <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">了解更多</span>
              </div>
              <div className="flex-1 grid grid-cols-2 items-center border border-[#ebebeb] rounded-sm px-4 py-2">
                <div className="border-r border-[#ebebeb]">
                  <div className="text-[13px] text-[#666]">过去7天返点 <InfoIcon tooltipText="如果您的 ROAS 未达到预期，平台将会以广告金的形式返还差异金额" /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">RM 0.00</div>
                </div>
                <div className="pl-6">
                  <div className="text-[13px] text-[#666]">受 ROAS 保护的广告 <InfoIcon tooltipText="当前正处于 ROAS 保护伞下的活跃广告数量" /></div>
                  <div className="text-[20px] font-bold text-[#333] mt-1">0</div>
                </div>
              </div>
            </div>
            <div className="bg-[#f5f5f5] text-[#555] text-[13px] px-3 py-2 rounded-[2px] flex items-center">
              <CheckCircleIcon /> 使用免费广告余额补齐 ROAS 差距
            </div>
          </div>

        </div>

        {/* 2. 推荐与广告奖励 */}
        <div className="grid grid-cols-[2fr_1fr] gap-4 mb-6">

          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5 relative overflow-hidden group/recs">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[16px] font-medium text-[#333]">推荐</h2>
              <div className="text-[13px] text-[#666]">
                11 个活跃项目 | <span className="text-[#05a] cursor-pointer hover:underline ml-1">查看全部 <ChevronRightIcon /></span>
              </div>
            </div>

            <div className="overflow-hidden w-full relative">
              <div
                className="flex transition-transform duration-500 ease-out w-full"
                style={{ transform: `translateX(calc(-${recIndex} * (50% + 8px)))` }}
              >
                {recommendationsData.map((rec) => (
                  <div
                    key={rec.id}
                    className="w-[calc(50%-8px)] flex-shrink-0 mr-4 last:mr-0 border border-[#ebebeb] rounded-sm p-4 bg-gradient-to-br from-white to-[#fff6f4] relative overflow-hidden h-[155px] flex flex-col justify-between"
                  >
                    <div className="flex items-start gap-3 relative z-10">
                      <div className="mt-0.5 w-6 h-6 rounded bg-[#ee4d2d] flex items-center justify-center flex-shrink-0 text-white shadow-sm">
                        {rec.icon}
                      </div>
                      <div>
                        <h3 className="text-[14px] font-bold text-[#333] leading-snug">{rec.title}</h3>
                        <p className="text-[13px] text-[#666] mt-1.5 leading-relaxed line-clamp-3">{rec.desc}</p>
                      </div>
                    </div>
                    <div className="flex justify-end relative z-10">
                      <button className="border border-[#ee4d2d] text-[#ee4d2d] bg-white px-5 py-1.5 rounded-[2px] text-[13px] hover:bg-[#fff6f4] transition-colors font-medium">
                        {rec.btnText}
                      </button>
                    </div>
                    <div className="absolute right-[-20px] bottom-[-20px] w-32 h-32 bg-[#ffedea] transform rotate-45 z-0"></div>
                  </div>
                ))}
              </div>
            </div>

            {recIndex > 0 && (
              <div
                onClick={() => setRecIndex(p => Math.max(0, p - 1))}
                className="absolute left-1 top-1/2 mt-3 w-8 h-8 bg-white rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.15)] flex items-center justify-center cursor-pointer z-20 text-[#666] hover:text-[#ee4d2d] transition-colors"
              >
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none"><polyline points="15 18 9 12 15 6"></polyline></svg>
              </div>
            )}

            {recIndex < recommendationsData.length - 2 && (
              <div
                onClick={() => setRecIndex(p => Math.min(recommendationsData.length - 2, p + 1))}
                className="absolute right-1 top-1/2 mt-3 w-8 h-8 bg-white rounded-full shadow-[0_2px_8px_rgba(0,0,0,0.15)] flex items-center justify-center cursor-pointer z-20 text-[#666] hover:text-[#ee4d2d] transition-colors"
              >
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none"><polyline points="9 18 15 12 9 6"></polyline></svg>
              </div>
            )}
          </div>

          <div className="bg-white rounded-sm shadow-sm border border-[#ebebeb] p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[16px] font-medium text-[#333]">广告奖励</h2>
              <span className="text-[13px] text-[#05a] cursor-pointer hover:underline flex items-center">更多 <ChevronRightIcon /></span>
            </div>
            <div className="border border-[#ebebeb] rounded-sm p-4 relative overflow-hidden h-[155px] flex flex-col justify-between">
              <div>
                <h3 className="text-[14px] font-medium text-[#333]">充值 RM 100 广告余额</h3>
                <div className="flex items-center gap-1.5 mt-2">
                  <div className="w-4 h-4 rounded-full bg-[#ee4d2d] text-white flex items-center justify-center text-[10px] font-bold">$</div>
                  <span className="text-[13px] text-[#666]">获得 <span className="text-[#ee4d2d] font-medium">RM 40</span> 免费广告余额</span>
                </div>
              </div>
              <div className="flex items-center justify-between mt-4">
                <span className="text-[12px] text-[#ee4d2d]">在 8 小时内过期</span>
                <button className="border border-[#ee4d2d] text-[#ee4d2d] bg-white px-6 py-1.5 rounded-sm text-[13px] hover:bg-[#fff6f4]">充值</button>
              </div>
            </div>
          </div>
        </div>

        {/* 3. 广告表现 (All Ads Performance) */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-6">
          <div className="flex px-6 border-b border-[#ebebeb] text-[14px] pt-4">
            {['全部点击出价广告', '商品广告', '新商品广告', '店铺广告', '直播广告'].map((tab) => (
              <div
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`mr-8 pb-3 cursor-pointer relative transition-colors ${activeTab === tab ? 'text-[#ee4d2d] font-medium' : 'text-[#333] hover:text-[#ee4d2d]'}`}
              >
                {tab}
                {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-[#ee4d2d]"></div>}
              </div>
            ))}
          </div>

          <div className="p-6">
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-[18px] font-medium text-[#333]">所有广告表现</h2>
              <div className="flex items-center gap-3">
                <div className="border border-[#d9d9d9] px-3 py-1.5 rounded-sm text-[13px] text-[#333] flex items-center gap-2 cursor-pointer">
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                  昨天 (GMT+7)
                </div>
                <div className="border border-[#d9d9d9] px-3 py-1.5 rounded-sm text-[13px] text-[#333] flex items-center gap-2 cursor-pointer">
                  导出数据 <ChevronDownIcon />
                </div>
                <div className="border border-[#d9d9d9] px-3 py-1.5 rounded-sm text-[13px] text-[#999] flex items-center gap-2 cursor-pointer bg-[#fafafa]">
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                  更多指标 <ChevronDownIcon />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4 mb-6">
              {performanceMetrics.map((item) => {
                const isSelected = selectedMetrics.includes(item.label);
                return (
                  <div
                    key={item.label}
                    onClick={() => toggleMetric(item.label)}
                    className={`border border-[#ebebeb] rounded-[2px] p-4 shadow-sm border-t-[3px] cursor-pointer hover:bg-[#fafafa] transition-colors`}
                    style={{ borderTopColor: isSelected ? item.baseColor : '#e5e5e5' }}
                  >
                    <div className="text-[13px] text-[#666]">{item.label} <InfoIcon tooltipText={item.tooltip} /></div>
                    <div className="text-[24px] font-medium text-[#333] mt-2">{item.value}</div>
                  </div>
                );
              })}
            </div>

            <div
              className="relative mt-12 mb-4 px-2 select-none group/chart"
              onMouseMove={handleChartMouseMove}
              onMouseLeave={() => setHoverIndex(null)}
            >

              <div className="absolute -top-8 right-2 flex items-center gap-4 text-[12px]">
                {selectedMetrics.map(label => {
                  const metric = performanceMetrics.find(m => m.label === label);
                  if (!metric) return null;
                  return (
                    <span key={label} className="flex items-center gap-1.5 text-[#333]">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: metric.baseColor }}></div>
                      {label}
                    </span>
                  );
                })}
              </div>

              <div className="relative h-[280px] w-full flex flex-col justify-between pointer-events-none z-0">
                {[1, 2, 3, 4, 5, 6].map((line, i) => (
                  <div key={line} className={`w-full h-px ${i === 5 ? 'bg-transparent' : 'bg-[#f0f0f0]'}`}></div>
                ))}

                <div
                  className="absolute bottom-0 left-0 right-0 h-[2px] z-10 transition-colors duration-300"
                  style={{ backgroundColor: performanceMetrics.find(m => m.label === selectedMetrics[0])?.baseColor || '#e5e5e5' }}
                ></div>
              </div>

              <svg
                className="absolute top-0 left-2 right-2 h-[280px] w-[calc(100%-16px)] z-10 overflow-visible pointer-events-none"
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                preserveAspectRatio="none"
              >
                {selectedMetrics.map(key => {
                  const metric = performanceMetrics.find(m => m.label === key);
                  if (!metric) return null;
                  return (
                    <path
                      key={key}
                      d={getSmoothPath(key)}
                      fill="none"
                      stroke={metric.baseColor}
                      strokeWidth="2"
                      strokeLinejoin="round"
                    />
                  );
                })}

                {hoverIndex !== null && (
                  <>
                    <line
                      x1={hoverIndex * pointSpacing}
                      y1="0"
                      x2={hoverIndex * pointSpacing}
                      y2={svgHeight}
                      stroke="#d9d9d9"
                      strokeDasharray="4 4"
                      strokeWidth="1.5"
                    />
                    {selectedMetrics.map(key => {
                      const metric = performanceMetrics.find(m => m.label === key);
                      const val = mockChartData[hoverIndex][key as keyof typeof mockChartData[0]] as number;
                      const maxVal = chartMax[key as keyof typeof chartMax];
                      const yPos = svgHeight - (val / maxVal) * svgHeight;
                      return (
                        <circle
                          key={'dot-' + key}
                          cx={hoverIndex * pointSpacing}
                          cy={yPos}
                          r="4"
                          fill={metric?.baseColor}
                          stroke="#fff"
                          strokeWidth="1.5"
                        />
                      );
                    })}
                  </>
                )}
              </svg>

              {hoverIndex !== null && (
                <div
                  className="absolute top-2 z-20 bg-white border border-[#ebebeb] shadow-[0_4px_16px_rgba(0,0,0,0.12)] rounded-[2px] p-3 text-[12px] min-w-[150px] pointer-events-none"
                  style={{
                    left: `calc(${(hoverIndex / (mockChartData.length - 1)) * 100}% + 8px)`,
                    transform: hoverIndex > mockChartData.length / 2 ? 'translateX(calc(-100% - 24px))' : 'translateX(8px)'
                  }}
                >
                  <div className="text-[#999] mb-2">{mockChartData[hoverIndex].date}</div>
                  {selectedMetrics.map(key => {
                    const metric = performanceMetrics.find(m => m.label === key);
                    const rawVal = mockChartData[hoverIndex][key as keyof typeof mockChartData[0]] as number;
                    return (
                      <div key={key} className="flex justify-between items-center mb-1.5 last:mb-0 gap-6">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: metric?.baseColor }}></div>
                          <span className="text-[#555]">{key}</span>
                        </div>
                        <span className="font-medium text-[#333]">{formatTooltipValue(key, rawVal)}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="flex justify-between pt-3 text-[12px] text-[#999]">
                <span>01/02</span>
                <span>12/02</span>
                <span>23/02</span>
                <span>06/03</span>
                <span>17/03</span>
                <span>28/03</span>
                <span>08/04</span>
                <span>19/04</span>
              </div>

            </div>
          </div>
        </section>

        {/* 4. 广告列表 (All Ads List) */}
        <section className="bg-white rounded-sm shadow-sm border border-[#ebebeb] mb-10 overflow-hidden">
          <div className="p-6 pb-0">
            <h2 className="text-[18px] font-medium text-[#333] mb-5">广告列表</h2>

            {/* Filter Row 1 */}
            <div className="flex items-center justify-between mb-4 text-[13px]">
              <div className="flex items-center gap-6">
                <span className="text-[#666]">广告状态</span>
                <div className="flex gap-2">
                  {['全部', '计划中', '进行中', '暂停中', '已结束', '已删除'].map(status => (
                    <button
                      key={status}
                      onClick={() => setListTab(status)}
                      className={`px-4 py-1.5 rounded-full border transition-colors ${listTab === status ? 'border-[#ee4d2d] text-[#ee4d2d]' : 'border-transparent text-[#555] hover:bg-[#fafafa]'}`}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-[#555] cursor-pointer">
                  <input type="checkbox" className="w-4 h-4 rounded-sm border-[#ccc] accent-[#ee4d2d] cursor-pointer" />
                  仅显示受 ROAS 保护的广告
                </label>
                <span className="text-[#999] cursor-pointer hover:text-[#333]">展开所有筛选 <ChevronDownIcon /></span>
              </div>
            </div>

            {/* Filter Row 2 */}
            <div className="flex items-center gap-3 mb-5">
              <div className="flex items-center border border-[#d9d9d9] rounded-sm h-9 px-3 w-[300px] focus-within:border-[#ee4d2d]">
                <input type="text" placeholder="搜索广告名称，商品名称，商品 ID" className="flex-1 outline-none text-[13px]" />
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="#999" strokeWidth="2" fill="none"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              </div>
              <div className="flex-1 max-w-[240px] border border-[#d9d9d9] rounded-sm h-9 px-3 flex items-center justify-between text-[13px] text-[#555] cursor-pointer">
                <span>全部类型 ×</span> <ChevronDownIcon />
              </div>
              <div className="flex-1 max-w-[240px] border border-[#d9d9d9] rounded-sm h-9 px-3 flex items-center justify-between text-[13px] text-[#555] cursor-pointer">
                <span>全部诊断状态</span> <ChevronDownIcon />
              </div>
              <div className="ml-auto border border-[#d9d9d9] rounded-sm h-9 px-4 flex items-center gap-2 text-[13px] text-[#333] cursor-pointer hover:bg-[#fafafa]">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                选择指标
              </div>
            </div>
          </div>

          {/* Table Container with Sticky Left Column */}
          <div className="border border-[#ebebeb] rounded-sm w-full overflow-hidden mt-2">
            <div className="overflow-x-auto custom-scrollbar pb-2">
              <div className="min-w-[1900px]">

                {/* Table Header */}
                <div className={`grid ${tableGridCols} bg-[#fafafa] border-b border-[#ebebeb] text-[13px] text-[#666] font-medium items-stretch`}>
                  {/* Sticky Header Cell */}
                  <div className="sticky left-0 z-20 flex items-center bg-[#fafafa] pl-8 pr-4 py-3 border-r border-[#ebebeb] shadow-[1px_0_4px_rgba(0,0,0,0.05)]">
                    <div className="flex items-center mr-4"><input type="checkbox" className="w-4 h-4 rounded-sm border-[#ccc] accent-[#ee4d2d] cursor-pointer" /></div>
                    <div>广告信息</div>
                  </div>
                  {/* Scrollable Header Cells */}
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">日预算 <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">目标 ROAS <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">诊断 <InfoIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">花费 <InfoIcon /> <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">销售额 <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">ROAS <InfoIcon /> <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">曝光量 <InfoIcon /> <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">点击数 <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">点击率 (CTR) <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">订单数 <InfoIcon /> <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">转化率 <InfoIcon /> <SortIcon /></div>
                  <div className="px-2 py-3 flex items-center cursor-pointer hover:text-[#333]">售出商品数 <InfoIcon /> <SortIcon /></div>
                </div>

                {/* Table Body */}
                <div className="text-[13px] text-[#333]">
                  {adsList.map((row) => {
                    const isPaused = row.status === 'Paused';
                    const isEnded = row.status === 'Ended';

                    return (
                      <div key={row.id} className={`grid ${tableGridCols} border-b border-[#ebebeb] last:border-b-0 items-stretch group hover:bg-[#fafafa] transition-colors`}>

                        {/* Sticky Body Cell */}
                        <div className="sticky left-0 z-10 flex items-start bg-white group-hover:bg-[#fafafa] transition-colors pl-8 pr-4 border-r border-[#ebebeb] shadow-[1px_0_4px_rgba(0,0,0,0.05)]">
                          <div className="pt-2 mr-3 flex-shrink-0">
                            <input type="checkbox" className="w-4 h-4 rounded-sm border-[#ccc] accent-[#ee4d2d] cursor-pointer" />
                          </div>

                          <div className="flex gap-3 pr-2 min-w-0 flex-1">
                            <img src={row.image} alt="Ad" className="w-12 h-12 border border-[#ebebeb] rounded-sm object-cover bg-white flex-shrink-0" />
                            <div className="min-w-0 flex-1">
                              <div className="font-medium text-[#333] truncate flex items-center gap-1.5" title={row.name}>
                                {row.name}
                                {row.hasWarning && <WarningIcon />}
                              </div>
                              <div className="text-[12px] text-[#888] truncate mt-0.5">{row.type}</div>
                              <div className="text-[12px] text-[#888] truncate">{row.period}</div>

                              <div className="flex items-center gap-2 mt-1.5">
                                <span className="flex items-center gap-1 text-[12px]">
                                  <div className={`w-2 h-2 rounded-full ${isPaused ? 'bg-[#ffb537]' : isEnded ? 'bg-[#b2b2b2]' : 'bg-[#26b562]'}`}></div>
                                  {row.statusLabel}
                                </span>
                                {row.roasProtected && (
                                  <span className="border border-[#d9d9d9] text-[#999] px-1.5 py-[1px] rounded-sm text-[11px] flex items-center gap-1 bg-white">
                                    <ShieldIcon /> ROAS 保护
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Data Columns */}
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.budget}</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.targetRoas}</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.diagnosis}</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.expense}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.sales}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.roas}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.impressions}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.clicks}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.ctr}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.conversions}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.conversionRate}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>
                        <div className="px-2 pt-5"><div className="text-[13px] text-[#333] truncate">{row.itemsSold}</div><div className="text-[12px] text-[#999] mt-0.5">-</div></div>

                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          <div className="p-6 pt-4">
            {/* Pagination Placeholder */}
            <div className="flex items-center justify-end text-[13px] text-[#666] gap-2 mt-2">
              <button className="p-1 hover:text-[#333]">&lt;</button>
              <span className="px-2">1 / 8</span>
              <button className="p-1 hover:text-[#333]">&gt;</button>
              <div className="border border-[#d9d9d9] rounded-sm px-2 py-1 ml-2 flex items-center justify-between w-24 cursor-pointer bg-white">
                <span>20 / 页</span>
                <ChevronDownIcon />
              </div>
            </div>
          </div>
        </section>

        {/* 5. 底部广告教育区域 */}
        <section className="bg-[#fcfcfc] rounded-sm shadow-sm border border-[#ebebeb] p-6 mb-10">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-[16px] font-medium text-[#333]">广告教育</h2>
            <span className="text-[13px] text-[#05a] cursor-pointer hover:underline">了解更多</span>
          </div>
          <div className="grid grid-cols-4 gap-6 text-[13px] text-[#444]">
            <ul className="space-y-2 list-disc pl-4 marker:text-[#ccc]">
              <li className="cursor-pointer hover:text-[#ee4d2d]">商品广告介绍</li>
            </ul>
            <ul className="space-y-2 list-disc pl-4 marker:text-[#ccc]">
              <li className="cursor-pointer hover:text-[#ee4d2d]">如何选择合适的商品</li>
            </ul>
            <ul className="space-y-2 list-disc pl-4 marker:text-[#ccc]">
              <li className="cursor-pointer hover:text-[#ee4d2d]">店铺广告介绍</li>
            </ul>
            <ul className="space-y-2 list-disc pl-4 marker:text-[#ccc]">
              <li className="cursor-pointer hover:text-[#ee4d2d]">充值广告余额</li>
            </ul>
          </div>
        </section>

      </div>
    </div>
  );
}